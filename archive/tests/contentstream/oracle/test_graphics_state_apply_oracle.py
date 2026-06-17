"""Live PDFBox differential parity for the ``gs`` ExtGState merge.

Drives ``PDExtendedGraphicsState.copy_into_graphics_state(PDGraphicsState)``
— the merge that the content-stream ``gs`` operator performs — and compares
the resulting :class:`PDGraphicsState` field values against Apache PDFBox's
``PDExtendedGraphicsState.copyIntoGraphicsState(PDGraphicsState)`` via the
``GraphicsStateApplyProbe`` Java oracle.

Two ExtGState dictionaries are exercised:

* ``full``  — every mergeable parameter set
  (LW/LC/LJ/ML/D/RI/OP/op/OPM/FL/SM/SA/CA/ca/AIS/TK/BM).
* ``empty`` — only ``/Type``; the graphics state keeps its constructor
  defaults so the probe confirms the no-touch path.

Canonical line grammar (must match
``oracle/probes/GraphicsStateApplyProbe.java``)::

    lineWidth=<float>
    lineCap=<int>
    lineJoin=<int>
    miterLimit=<float>
    lineDashPattern=[<floats>] phase=<int>
    renderingIntent=<name|null>
    overprint=<bool>
    nonStrokingOverprint=<bool>
    overprintMode=<int>
    flatness=<float>
    smoothness=<float>
    strokeAdjustment=<bool>
    alphaConstant=<float>
    nonStrokeAlphaConstant=<float>
    alphaSource=<bool>
    textKnockout=<bool>
    blendMode=<name>
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
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from tests.oracle.harness import requires_oracle, run_probe_text


def _fmt(value: float) -> str:
    """Canonical float rendering matching the probe's ``fmt``."""
    f = float(value)
    if f == int(f):
        return str(int(f))
    s = f"{f:.6f}".rstrip("0").rstrip(".")
    return s


def _dash(pattern: object) -> str:
    arr = pattern.get_dash_array()  # type: ignore[attr-defined]
    inner = " ".join(_fmt(v) for v in arr)
    phase = int(pattern.get_phase())  # type: ignore[attr-defined]
    return f"[{inner}] phase={phase}"


def _ri(intent: object) -> str:
    if intent is None:
        return "null"
    return intent.string_value()  # type: ignore[attr-defined]


def _blend(mode: object) -> str:
    return mode.get_name()  # type: ignore[attr-defined]


def _build_full() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("ExtGState"))
    d.set_item(COSName.get_pdf_name("LW"), COSFloat(2.5))
    d.set_item(COSName.get_pdf_name("LC"), COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("LJ"), COSInteger.get(2))
    d.set_item(COSName.get_pdf_name("ML"), COSFloat(4.0))
    dash = COSArray()
    dash_arr = COSArray()
    dash_arr.add(COSFloat(3.0))
    dash_arr.add(COSFloat(2.0))
    dash.add(dash_arr)
    dash.add(COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("D"), dash)
    d.set_item(COSName.get_pdf_name("RI"), COSName.get_pdf_name("Perceptual"))
    d.set_item(COSName.get_pdf_name("OP"), COSBoolean.TRUE)
    d.set_item(COSName.get_pdf_name("op"), COSBoolean.TRUE)
    d.set_item(COSName.get_pdf_name("OPM"), COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("FL"), COSFloat(0.5))
    d.set_item(COSName.get_pdf_name("SM"), COSFloat(0.125))
    d.set_item(COSName.get_pdf_name("SA"), COSBoolean.TRUE)
    d.set_item(COSName.get_pdf_name("CA"), COSFloat(0.5))
    d.set_item(COSName.get_pdf_name("ca"), COSFloat(0.25))
    d.set_item(COSName.get_pdf_name("AIS"), COSBoolean.TRUE)
    d.set_item(COSName.get_pdf_name("TK"), COSBoolean.FALSE)
    d.set_item(COSName.get_pdf_name("BM"), COSName.get_pdf_name("Multiply"))
    return d


def _build_empty() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("ExtGState"))
    return d


def _emit(dictionary: COSDictionary) -> str:
    egs = PDExtendedGraphicsState(dictionary)
    gs = PDGraphicsState()
    egs.copy_into_graphics_state(gs)
    lines = [
        f"lineWidth={_fmt(gs.get_line_width())}",
        f"lineCap={gs.get_line_cap()}",
        f"lineJoin={gs.get_line_join()}",
        f"miterLimit={_fmt(gs.get_miter_limit())}",
        f"lineDashPattern={_dash(gs.get_line_dash_pattern())}",
        f"renderingIntent={_ri(gs.get_rendering_intent())}",
        f"overprint={str(gs.is_overprint()).lower()}",
        f"nonStrokingOverprint={str(gs.is_non_stroking_overprint()).lower()}",
        f"overprintMode={gs.get_overprint_mode()}",
        f"flatness={_fmt(gs.get_flatness())}",
        f"smoothness={_fmt(gs.get_smoothness())}",
        f"strokeAdjustment={str(gs.is_stroke_adjustment()).lower()}",
        f"alphaConstant={_fmt(gs.get_alpha_constant())}",
        f"nonStrokeAlphaConstant={_fmt(gs.get_non_stroke_alpha_constant())}",
        f"alphaSource={str(gs.is_alpha_source()).lower()}",
        f"textKnockout="
        f"{str(gs.get_text_state().get_knockout_flag()).lower()}",
        f"blendMode={_blend(gs.get_blend_mode())}",
    ]
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize("mode", ["full", "empty"])
def test_copy_into_graphics_state_matches_pdfbox(mode: str) -> None:
    builder = _build_full if mode == "full" else _build_empty
    java = run_probe_text("GraphicsStateApplyProbe", mode)
    py = _emit(builder())
    assert py == java
