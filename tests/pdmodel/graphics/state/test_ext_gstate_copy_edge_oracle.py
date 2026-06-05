"""Live PDFBox differential parity for ``copyIntoGraphicsState`` edge cases.

Mirrors ``oracle/probes/GraphicsStateApplyEdgeProbe.java``: each mode seeds a
``PDGraphicsState`` with a non-default value, applies an ExtGState carrying a
present-but-malformed entry, and asserts pypdfbox lands the same result as
Apache PDFBox 3.0.7.

Modes:

* ``malformed_d``   — a size-1 ``/D`` clears the seeded dash (``dash=null``).
* ``tr_tr2``        — ``/TR2`` wins over ``/TR`` (``transfer=arr:TR2mark``).
* ``tr_malformed``  — a size-3 ``/TR`` clears the seeded transfer
  (``transfer=null``).
* ``wrong_lw``      — a non-numeric ``/LW`` pushes the spec default
  (``lineWidth=1``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from tests.oracle.harness import requires_oracle, run_probe_text


def _base() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("ExtGState"))
    return d


def _arr4(marker: str) -> COSArray:
    a = COSArray()
    for _ in range(4):
        a.add(COSName.get_pdf_name(marker))
    return a


def _marker(base: object) -> str:
    if base is None:
        return "null"
    if isinstance(base, COSName):
        return "name:" + base.get_name()
    if isinstance(base, COSArray) and base.size() > 0:
        first = base.get_object(0)
        if isinstance(first, COSName):
            return "arr:" + first.get_name()
    return str(base)


def _dash(pattern: object) -> str:
    if pattern is None:
        return "null"
    arr = pattern.get_dash_array()  # type: ignore[attr-defined]

    def fmt(v: float) -> str:
        f = float(v)
        return str(int(f)) if f == int(f) else f"{f:.6f}".rstrip("0").rstrip(".")

    inner = " ".join(fmt(v) for v in arr)
    phase = int(pattern.get_phase())  # type: ignore[attr-defined]
    return f"[{inner}] phase={phase}"


def _emit(mode: str) -> str:
    if mode == "malformed_d":
        gs = PDGraphicsState()
        seed = COSArray()
        seed.add(COSFloat(7.0))
        seed.add(COSFloat(7.0))
        gs.set_line_dash_pattern(PDLineDashPattern(seed, 9))
        d = _base()
        mal = COSArray()
        mal.add(COSInteger.get(1))
        d.set_item(COSName.get_pdf_name("D"), mal)
        PDExtendedGraphicsState(d).copy_into_graphics_state(gs)
        return "dash=" + _dash(gs.get_line_dash_pattern()) + "\n"
    if mode == "tr_tr2":
        gs = PDGraphicsState()
        d = _base()
        d.set_item(COSName.get_pdf_name("TR"), _arr4("TRmark"))
        d.set_item(COSName.get_pdf_name("TR2"), _arr4("TR2mark"))
        PDExtendedGraphicsState(d).copy_into_graphics_state(gs)
        return "transfer=" + _marker(gs.get_transfer()) + "\n"
    if mode == "tr_malformed":
        gs = PDGraphicsState()
        gs.set_transfer(COSName.get_pdf_name("seeded"))
        d = _base()
        three = COSArray()
        for name in ("a", "b", "c"):
            three.add(COSName.get_pdf_name(name))
        d.set_item(COSName.get_pdf_name("TR"), three)
        PDExtendedGraphicsState(d).copy_into_graphics_state(gs)
        return "transfer=" + _marker(gs.get_transfer()) + "\n"
    if mode == "wrong_lw":
        gs = PDGraphicsState()
        gs.set_line_width(42)
        d = _base()
        d.set_item(COSName.get_pdf_name("LW"), COSName.get_pdf_name("notanumber"))
        PDExtendedGraphicsState(d).copy_into_graphics_state(gs)
        lw = gs.get_line_width()
        rendered = str(int(lw)) if float(lw) == int(lw) else f"{lw:.6f}"
        return "lineWidth=" + rendered + "\n"
    if mode == "wrong_opm":
        gs = PDGraphicsState()
        gs.set_overprint_mode(7)
        d = _base()
        d.set_item(COSName.get_pdf_name("OPM"), COSName.get_pdf_name("notanumber"))
        PDExtendedGraphicsState(d).copy_into_graphics_state(gs)
        return "overprintMode=" + str(gs.get_overprint_mode()) + "\n"
    if mode == "wrong_ri":
        from pypdfbox.pdmodel.graphics.state.rendering_intent import RenderingIntent

        gs = PDGraphicsState()
        gs.set_rendering_intent(RenderingIntent.SATURATION)
        d = _base()
        d.set_item(COSName.get_pdf_name("RI"), COSInteger.get(5))
        PDExtendedGraphicsState(d).copy_into_graphics_state(gs)
        ri = gs.get_rendering_intent()
        return "renderingIntent=" + ("null" if ri is None else ri.string_value()) + "\n"
    raise ValueError(mode)


@requires_oracle
@pytest.mark.parametrize(
    "mode",
    [
        "malformed_d",
        "tr_tr2",
        "tr_malformed",
        "wrong_lw",
        "wrong_opm",
        "wrong_ri",
    ],
)
def test_copy_edge_matches_pdfbox(mode: str) -> None:
    java = run_probe_text("GraphicsStateApplyEdgeProbe", mode)
    assert _emit(mode) == java
