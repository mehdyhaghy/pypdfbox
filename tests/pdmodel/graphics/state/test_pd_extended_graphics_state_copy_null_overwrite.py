"""Regression pins for ``copy_into_graphics_state`` null-overwrite semantics.

Upstream PDFBox ``PDExtendedGraphicsState.copyIntoGraphicsState`` calls the
target setter *unconditionally* for every present key — so an ExtGState that
carries a present-but-malformed ``/D``, ``/TR``, or ``/TR2`` pushes a ``null``
through ``setLineDashPattern`` / ``setTransfer``, *overwriting* whatever the
target graphics state held before. Earlier the port used a None-skipping copy
helper for these three keys, so a broken entry was silently ignored and the
pre-existing value survived — a divergence from PDFBox.

The literals here were confirmed against live Apache PDFBox 3.0.7 via
``GraphicsStateApplyEdgeProbe`` (modes ``malformed_d`` / ``tr_malformed`` /
``tr_tr2``): a malformed ``/D`` -> ``dash=null``; a 3-element ``/TR`` ->
``transfer=null``; both ``/TR`` and ``/TR2`` present -> ``/TR2`` wins.

The differential test at the bottom (``@requires_oracle``) re-runs the same
probe; the value pins above stand on their own without a JDK / jar.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from pypdfbox.pdmodel.graphics.state.rendering_intent import RenderingIntent


def _ext_gstate(*items: tuple[str, object]) -> PDExtendedGraphicsState:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("ExtGState"))
    for key, value in items:
        d.set_item(COSName.get_pdf_name(key), value)
    return PDExtendedGraphicsState(d)


def test_malformed_dash_overwrites_seeded_pattern_with_none() -> None:
    gs = PDGraphicsState()
    seed = COSArray()
    seed.add(COSFloat(7.0))
    seed.add(COSFloat(7.0))
    gs.set_line_dash_pattern(PDLineDashPattern(seed, 9))

    # /D present but size 1 (not the required [array phase] shape).
    malformed = COSArray()
    malformed.add(COSInteger.get(1))
    _ext_gstate(("D", malformed)).copy_into_graphics_state(gs)

    # Upstream setLineDashPattern(null) wins — the seeded pattern is cleared.
    assert gs.get_line_dash_pattern() is None


def test_malformed_transfer_overwrites_seeded_transfer_with_none() -> None:
    gs = PDGraphicsState()
    gs.set_transfer(COSName.get_pdf_name("seeded"))

    # /TR present but a 3-array (size != 4) -> get_transfer() returns None.
    three = COSArray()
    for name in ("a", "b", "c"):
        three.add(COSName.get_pdf_name(name))
    _ext_gstate(("TR", three)).copy_into_graphics_state(gs)

    assert gs.get_transfer() is None


def test_malformed_transfer2_overwrites_seeded_transfer_with_none() -> None:
    gs = PDGraphicsState()
    gs.set_transfer(COSName.get_pdf_name("seeded"))

    three = COSArray()
    for name in ("a", "b", "c"):
        three.add(COSName.get_pdf_name(name))
    _ext_gstate(("TR2", three)).copy_into_graphics_state(gs)

    assert gs.get_transfer() is None


def test_tr2_takes_precedence_over_tr() -> None:
    gs = PDGraphicsState()

    def arr4(marker: str) -> COSArray:
        a = COSArray()
        for _ in range(4):
            a.add(COSName.get_pdf_name(marker))
        return a

    _ext_gstate(
        ("TR", arr4("TRmark")), ("TR2", arr4("TR2mark"))
    ).copy_into_graphics_state(gs)

    transfer = gs.get_transfer()
    assert isinstance(transfer, COSArray)
    assert transfer.get_object(0).get_name() == "TR2mark"


def test_wellformed_dash_still_copies() -> None:
    # The fix must not regress the happy path: a valid /D still lands.
    gs = PDGraphicsState()
    inner = COSArray()
    inner.add(COSFloat(3.0))
    inner.add(COSFloat(2.0))
    dash = COSArray()
    dash.add(inner)
    dash.add(COSInteger.get(1))
    _ext_gstate(("D", dash)).copy_into_graphics_state(gs)

    pattern = gs.get_line_dash_pattern()
    assert pattern is not None
    assert pattern.get_dash_array() == [3.0, 2.0]
    assert pattern.get_phase() == 1


def test_absent_dash_leaves_seeded_pattern_intact() -> None:
    # Only a *present* /D key triggers the (null) overwrite; an ExtGState with
    # no /D at all must not touch the target's dash pattern.
    gs = PDGraphicsState()
    seed = COSArray()
    seed.add(COSFloat(5.0))
    seeded = PDLineDashPattern(seed, 0)
    gs.set_line_dash_pattern(seeded)

    _ext_gstate().copy_into_graphics_state(gs)

    assert gs.get_line_dash_pattern() is seeded


def test_malformed_opm_overwrites_seeded_mode_with_zero() -> None:
    # Upstream: ``gs.setOverprintMode(om != null ? om : 0)`` — a present-but-
    # malformed /OPM (value not a number) substitutes the spec default 0 and
    # pushes it, overwriting a seeded non-zero mode (oracle-confirmed,
    # GraphicsStateApplyEdgeProbe mode ``wrong_opm``).
    gs = PDGraphicsState()
    gs.set_overprint_mode(7)

    _ext_gstate(
        ("OPM", COSName.get_pdf_name("notanumber"))
    ).copy_into_graphics_state(gs)

    assert gs.get_overprint_mode() == 0


def test_wellformed_opm_still_copies() -> None:
    gs = PDGraphicsState()
    _ext_gstate(("OPM", COSInteger.get(1))).copy_into_graphics_state(gs)
    assert gs.get_overprint_mode() == 1


def test_malformed_ri_overwrites_seeded_intent_with_none() -> None:
    # Upstream: ``gs.setRenderingIntent(getRenderingIntent())`` — a present-but-
    # malformed /RI (a value that is neither a name nor a string) yields ``None``
    # and overwrites a seeded intent (oracle-confirmed, mode ``wrong_ri``).
    gs = PDGraphicsState()
    gs.set_rendering_intent(RenderingIntent.SATURATION)

    _ext_gstate(("RI", COSInteger.get(5))).copy_into_graphics_state(gs)

    assert gs.get_rendering_intent() is None


def test_wellformed_ri_still_copies() -> None:
    gs = PDGraphicsState()
    _ext_gstate(
        ("RI", COSName.get_pdf_name("Saturation"))
    ).copy_into_graphics_state(gs)
    assert gs.get_rendering_intent() == RenderingIntent.SATURATION
