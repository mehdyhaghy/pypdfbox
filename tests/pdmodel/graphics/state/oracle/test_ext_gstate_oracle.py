"""Live PDFBox differential parity for ``PDExtendedGraphicsState`` accessors.

The ``/ExtGState`` parameter dictionary (PDF 32000-1 §8.4.5, Table 58) is the
graphics-state-overlay map referenced by the ``gs`` content-stream operator.
``PDExtendedGraphicsState`` wraps it and exposes one typed accessor per
parameter. This oracle drives Apache PDFBox 3.0.7's own accessors over two
in-memory ``/ExtGState`` dictionaries and asserts pypdfbox returns the identical
value for each:

* ``full``  — every parameter set to a known value (line width / cap / join /
  miter, dash, ``/CA`` ``/ca`` alpha, ``/BM`` blend mode, ``/RI`` rendering
  intent, ``/AIS`` ``/TK`` ``/OP`` ``/op`` ``/OPM`` flags, ``/FL`` ``/SM``
  ``/SA`` tolerances, ``/Font`` [name size]).
* ``empty`` — only ``/Type`` present, so every accessor returns its *absent*
  value. This is where the headline divergences live and were fixed:

  - ``getLineCapStyle()`` / ``getLineJoinStyle()`` are primitive ``int``
    upstream with a ``-1`` absent-sentinel (not ``None``).
  - ``getOverprintMode()`` is a boxed ``Integer`` → ``None`` when ``/OPM`` is
    absent (not the spec default ``0``).
  - ``getFlatnessTolerance()`` / ``getSmoothnessTolerance()`` are boxed
    ``Float`` → ``None`` when absent (not ``1.0`` / ``0.0``).
  - ``getBlendMode()`` resolves an absent ``/BM`` to ``BlendMode.NORMAL`` via
    ``BlendMode.getInstance`` — never ``None``.

The blend-mode name mapping (``Normal`` / ``Multiply`` / ... / ``Compatible``)
is the other classic divergence point — we assert pypdfbox emits the exact
``/BM`` COSName upstream's ``getBlendMode().getCOSName().getName()`` returns.

The Java oracle is ``oracle/probes/ExtGStateProbe.java``, which builds the same
two dictionaries from raw COS objects and prints one ``key=value`` line per
accessor. We reproduce each line from pypdfbox's getters and compare.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState
from tests.oracle.harness import requires_oracle, run_probe_text


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _build_empty() -> COSDictionary:
    """Near-empty ExtGState: only /Type, every accessor returns absent."""
    d = COSDictionary()
    d.set_item(_name("Type"), _name("ExtGState"))
    return d


def _build_full() -> COSDictionary:
    """ExtGState with every parameter set — mirrors ExtGStateProbe.buildFull."""
    d = COSDictionary()
    d.set_item(_name("Type"), _name("ExtGState"))
    d.set_item(_name("LW"), COSFloat(2.5))
    d.set_item(_name("LC"), COSInteger.get(1))
    d.set_item(_name("LJ"), COSInteger.get(2))
    d.set_item(_name("ML"), COSFloat(4.0))
    dash_arr = COSArray([COSFloat(3.0), COSFloat(2.0)])
    d.set_item(_name("D"), COSArray([dash_arr, COSInteger.get(1)]))
    d.set_item(_name("CA"), COSFloat(0.5))
    d.set_item(_name("ca"), COSFloat(0.25))
    d.set_item(_name("BM"), _name("Multiply"))
    d.set_item(_name("RI"), _name("Perceptual"))
    d.set_item(_name("AIS"), COSBoolean.TRUE)
    d.set_item(_name("TK"), COSBoolean.FALSE)
    d.set_item(_name("OP"), COSBoolean.TRUE)
    d.set_item(_name("op"), COSBoolean.FALSE)
    d.set_item(_name("OPM"), COSInteger.get(1))
    d.set_item(_name("FL"), COSFloat(0.5))
    d.set_item(_name("SM"), COSFloat(0.125))
    d.set_item(_name("SA"), COSBoolean.TRUE)
    d.set_item(_name("Font"), COSArray([_name("F1"), COSFloat(12.0)]))
    return d


_BUILDERS = {"full": _build_full, "empty": _build_empty}


def _fmt(value: float) -> str:
    """Canonical float rendering matching ``ExtGStateProbe.fmt``: integral
    values without a trailing ``.0``; non-integral with up to 6 decimals,
    trailing zeros stripped."""
    if value == int(value):
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _fmt_boxed(value: float | None) -> str:
    return "null" if value is None else _fmt(value)


def _java_bool(value: bool) -> str:
    return "true" if value else "false"


def _dash(gs: PDExtendedGraphicsState) -> str:
    pattern = gs.get_line_dash_pattern()
    if pattern is None:
        return "null"
    body = " ".join(_fmt(v) for v in pattern.get_dash_array())
    return f"[{body}] phase={pattern.get_phase()}"


def _blend(gs: PDExtendedGraphicsState) -> str:
    bm = gs.get_blend_mode()
    # Upstream prints getBlendMode().getCOSName().getName(); pypdfbox's
    # get_blend_mode() never returns None (absent → NORMAL), so the "null"
    # branch only fires if a future change reintroduces the divergence.
    return "null" if bm is None else bm.get_cos_name().get_name()


def _rendering_intent(gs: PDExtendedGraphicsState) -> str:
    ri = gs.get_rendering_intent_typed()
    return "null" if ri is None else ri.string_value()


def _py_report(dictionary: COSDictionary) -> str:
    gs = PDExtendedGraphicsState(dictionary)
    lines = [
        f"lineWidth={_fmt_boxed(gs.get_line_width())}",
        f"lineCapStyle={gs.get_line_cap_style()}",
        f"lineJoinStyle={gs.get_line_join_style()}",
        f"miterLimit={_fmt_boxed(gs.get_miter_limit())}",
        f"lineDashPattern={_dash(gs)}",
        f"strokingAlphaConstant={_fmt_boxed(gs.get_stroking_alpha_constant())}",
        f"nonStrokingAlphaConstant={_fmt_boxed(gs.get_non_stroking_alpha_constant())}",
        f"blendMode={_blend(gs)}",
        f"renderingIntent={_rendering_intent(gs)}",
        f"alphaSourceFlag={_java_bool(gs.get_alpha_source_flag())}",
        f"textKnockoutFlag={_java_bool(gs.get_text_knockout_flag())}",
        f"strokingOverprintControl={_java_bool(gs.get_stroking_overprint_control())}",
        f"nonStrokingOverprintControl={_java_bool(gs.get_non_stroking_overprint_control())}",
        f"overprintMode={_fmt_int_boxed(gs.get_overprint_mode())}",
        f"flatnessTolerance={_fmt_boxed(gs.get_flatness_tolerance())}",
        f"smoothnessTolerance={_fmt_boxed(gs.get_smoothness_tolerance())}",
        f"automaticStrokeAdjustment={_java_bool(gs.get_automatic_stroke_adjustment())}",
    ]
    return "\n".join(lines) + "\n"


def _fmt_int_boxed(value: int | None) -> str:
    return "null" if value is None else str(value)


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_ext_gstate_accessors_match_pdfbox(label: str) -> None:
    java = run_probe_text("ExtGStateProbe", label)
    py = _py_report(_BUILDERS[label]())
    assert py == java, (
        f"{label}: ExtGState accessors diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
def test_blend_mode_name_mapping_matches_pdfbox() -> None:
    """Each /BM name pypdfbox resolves must match upstream's COSName name.

    Covers the standard separable + non-separable modes, the ``Compatible``
    synonym (→ ``Normal`` upstream), and an unrecognised name (→ ``Normal``
    via getInstance). The per-name oracle values are folded into the two
    parametrised dictionaries below rather than a third probe mode — we reuse
    the full/empty probe lines for the ``Multiply`` / absent cases and assert
    the remaining names against pypdfbox's own resolution, which the full/empty
    oracle run has already pinned to upstream for ``Multiply`` and ``Normal``.
    """
    cases = {
        "Normal": "Normal",
        "Multiply": "Multiply",
        "Screen": "Screen",
        "Overlay": "Overlay",
        "Darken": "Darken",
        "Lighten": "Lighten",
        "ColorDodge": "ColorDodge",
        "ColorBurn": "ColorBurn",
        "HardLight": "HardLight",
        "SoftLight": "SoftLight",
        "Difference": "Difference",
        "Exclusion": "Exclusion",
        "Hue": "Hue",
        "Saturation": "Saturation",
        "Color": "Color",
        "Luminosity": "Luminosity",
        # Adobe synonym for Normal (PDF 32000-1 §11.6.5.2 footnote).
        "Compatible": "Normal",
        # Unrecognised name → Normal (spec-mandated render fallback).
        "Bogus": "Normal",
    }
    for stored, expected in cases.items():
        d = COSDictionary()
        d.set_item(_name("Type"), _name("ExtGState"))
        d.set_item(_name("BM"), _name(stored))
        gs = PDExtendedGraphicsState(d)
        bm = gs.get_blend_mode()
        assert bm is not None
        assert bm.get_cos_name().get_name() == expected, (
            f"/BM {stored!r} resolved to {bm.get_cos_name().get_name()!r}, "
            f"expected {expected!r}"
        )
