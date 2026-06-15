"""Differential oracle for the ``PDGraphicsState`` object's OWN behaviour vs
Apache PDFBox 3.0.7 (wave 1536, agent C).

The existing ``GraphicsStateApplyProbe`` suites exercise applying an
``/ExtGState`` dict TO a state via ``copyIntoGraphicsState``. This audit covers
the orthogonal angle: the ``PDGraphicsState`` constructor field defaults,
``clone()`` deep/shallow field independence, and setter storage of edge values.

Java (``oracle/probes/GraphicsStateObjectFuzzProbe.java``) is ground truth. This
module projects the identical grammar through pypdfbox and asserts line-for-line
parity for each of the three probe modes:

* ``defaults`` — every field on a fresh ``PDGraphicsState(PDRectangle())``.
* ``clone``    — whether mutating a clone touches the original (CTM / text
  matrix / text state are deep-cloned; colours / dash / clipping list are
  shared references; scalars are independent).
* ``setters``  — negative line width, alpha out of ``[0, 1]``, ``NaN``,
  ``±Infinity``, huge / negative ints stored verbatim.

Confirmed from the 3.0.7 bytecode (``javap -c PDGraphicsState``): ``clone()``
deep-clones ``textState``, ``currentTransformationMatrix``, and (when non-null)
``textMatrix`` / ``textLineMatrix``; it re-assigns ``strokingColor``,
``nonStrokingColor``, ``lineDashPattern``, ``clippingPaths`` and
``clippingPathCache`` by the SAME reference, and resets ``isClippingPathDirty``
to false. A real divergence is a production fix in
``pypdfbox/pdmodel/graphics/state/pd_graphics_state.py``.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.util.matrix import Matrix
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "GraphicsStateObjectFuzzProbe"


def _fmt(value: float) -> str:
    """Mirror the Java probe's ``fmt(double)`` canonical float rendering."""
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    if value == math.floor(value):
        return str(int(value))
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _matrix(matrix: object) -> str:
    return str(matrix)


def _color(color: object) -> str:
    if color is None:
        return "null"
    comps = color.get_components()
    return "[" + " ".join(_fmt(float(component)) for component in comps) + "]"


def _cs(color_space: object) -> str:
    return "null" if color_space is None else color_space.get_name()


def _dash(pattern: object) -> str:
    if pattern is None:
        return "null"
    arr = pattern.get_dash_array()
    body = " ".join(_fmt(float(value)) for value in arr)
    return f"[{body}] phase={pattern.get_phase()}"


def _blend(blend_mode: object) -> str:
    if blend_mode is None:
        return "null"
    name = getattr(blend_mode, "get_name", None)
    if callable(name):
        return name()
    return getattr(blend_mode, "name", str(blend_mode))


def _ri(intent: object) -> str:
    if intent is None:
        return "null"
    string_value = getattr(intent, "string_value", None)
    if callable(string_value):
        return string_value()
    return str(intent)


def _rendering_mode(mode: object) -> str:
    # Java prints the enum constant name (e.g. "FILL"); Python's str() yields
    # "RenderingMode.FILL". Project the bare constant name for parity.
    return getattr(mode, "name", str(mode))


def _opt_matrix(matrix: object) -> str:
    return "null" if matrix is None else _matrix(matrix)


def _py_defaults() -> list[str]:
    gs = PDGraphicsState(PDRectangle())
    ts = gs.get_text_state()
    return [
        f"lineWidth={_fmt(gs.get_line_width())}",
        f"lineCap={gs.get_line_cap()}",
        f"lineJoin={gs.get_line_join()}",
        f"miterLimit={_fmt(gs.get_miter_limit())}",
        f"strokeAdjustment={_bool(gs.is_stroke_adjustment())}",
        f"alphaConstant={_fmt(gs.get_alpha_constant())}",
        f"nonStrokeAlphaConstant={_fmt(gs.get_non_stroke_alpha_constant())}",
        f"alphaSource={_bool(gs.is_alpha_source())}",
        f"overprint={_bool(gs.is_overprint())}",
        f"nonStrokingOverprint={_bool(gs.is_non_stroking_overprint())}",
        f"overprintMode={gs.get_overprint_mode()}",
        f"flatness={_fmt(gs.get_flatness())}",
        f"smoothness={_fmt(gs.get_smoothness())}",
        f"blendMode={_blend(gs.get_blend_mode())}",
        f"renderingIntent={_ri(gs.get_rendering_intent())}",
        f"softMask={'null' if gs.get_soft_mask() is None else 'set'}",
        f"transfer={'null' if gs.get_transfer() is None else 'set'}",
        f"textMatrix={_opt_matrix(gs.get_text_matrix())}",
        f"textLineMatrix={_opt_matrix(gs.get_text_line_matrix())}",
        f"ctm={_matrix(gs.get_current_transformation_matrix())}",
        f"strokingColor={_color(gs.get_stroking_color())}",
        f"nonStrokingColor={_color(gs.get_non_stroking_color())}",
        f"strokingColorSpace={_cs(gs.get_stroking_color_space())}",
        f"nonStrokingColorSpace={_cs(gs.get_non_stroking_color_space())}",
        f"dash={_dash(gs.get_line_dash_pattern())}",
        f"ts.characterSpacing={_fmt(ts.get_character_spacing())}",
        f"ts.wordSpacing={_fmt(ts.get_word_spacing())}",
        f"ts.horizontalScaling={_fmt(ts.get_horizontal_scaling())}",
        f"ts.leading={_fmt(ts.get_leading())}",
        f"ts.fontSize={_fmt(ts.get_font_size())}",
        f"ts.rise={_fmt(ts.get_rise())}",
        f"ts.renderingMode={_rendering_mode(ts.get_rendering_mode())}",
        f"ts.knockout={_bool(ts.get_knockout_flag())}",
        f"ts.font={'null' if ts.get_font() is None else 'set'}",
    ]


def _py_clone() -> list[str]:
    orig = PDGraphicsState(PDRectangle(0, 0, 100, 100))
    orig.set_text_matrix(Matrix())
    orig.set_text_line_matrix(Matrix())
    clone = orig.clone()

    clone.get_current_transformation_matrix().set_value(0, 0, 9.0)
    ctm_shared = orig.get_current_transformation_matrix().get_value(0, 0) == 9.0

    clone.get_text_matrix().set_value(0, 0, 7.0)
    text_matrix_shared = orig.get_text_matrix().get_value(0, 0) == 7.0

    clone.get_text_state().set_font_size(42.0)
    text_state_shared = orig.get_text_state().get_font_size() == 42.0

    clone.set_line_width(5.0)
    line_width_independent = orig.get_line_width() == 1.0

    text_state_same = orig.get_text_state() is clone.get_text_state()
    stroking_same = orig.get_stroking_color() is clone.get_stroking_color()
    ns_same = orig.get_non_stroking_color() is clone.get_non_stroking_color()
    dash_same = orig.get_line_dash_pattern() is clone.get_line_dash_pattern()
    ctm_same = (
        orig.get_current_transformation_matrix()
        is clone.get_current_transformation_matrix()
    )
    clip_same = orig.get_current_clipping_paths() is clone.get_current_clipping_paths()

    return [
        f"ctm_shared={_bool(ctm_shared)}",
        f"textMatrix_shared={_bool(text_matrix_shared)}",
        f"textState_shared={_bool(text_state_shared)}",
        f"textState_sameRef={_bool(text_state_same)}",
        f"strokingColor_sameRef={_bool(stroking_same)}",
        f"nonStrokingColor_sameRef={_bool(ns_same)}",
        f"dash_sameRef={_bool(dash_same)}",
        f"ctm_sameRef={_bool(ctm_same)}",
        f"clipping_sameRef={_bool(clip_same)}",
        f"lineWidth_independent={_bool(line_width_independent)}",
    ]


def _py_setters() -> list[str]:
    gs = PDGraphicsState(PDRectangle())
    gs.set_line_width(-3.5)
    line_width_neg = _fmt(gs.get_line_width())
    gs.set_miter_limit(-1.0)
    miter_neg = _fmt(gs.get_miter_limit())
    gs.set_line_cap(99)
    line_cap_big = gs.get_line_cap()
    gs.set_line_join(-5)
    line_join_neg = gs.get_line_join()
    gs.set_alpha_constant(2.5)
    alpha_over = _fmt(gs.get_alpha_constant())
    gs.set_non_stroke_alpha_constant(-0.5)
    ns_alpha_neg = _fmt(gs.get_non_stroke_alpha_constant())
    gs.set_alpha_constant(float("nan"))
    alpha_nan = "NaN" if math.isnan(gs.get_alpha_constant()) else _fmt(gs.get_alpha_constant())
    gs.set_flatness(float("inf"))
    flatness_inf = "Infinity" if gs.get_flatness() == float("inf") else _fmt(gs.get_flatness())
    gs.set_smoothness(-7.0)
    smoothness_neg = _fmt(gs.get_smoothness())
    gs.set_overprint_mode(-2)
    opm_neg = gs.get_overprint_mode()
    gs.set_line_width(float("nan"))
    line_width_nan = "NaN" if math.isnan(gs.get_line_width()) else _fmt(gs.get_line_width())
    gs.set_line_width(float("inf"))
    line_width_inf = (
        "Infinity" if gs.get_line_width() == float("inf") else _fmt(gs.get_line_width())
    )

    return [
        f"lineWidth_neg={line_width_neg}",
        f"miterLimit_neg={miter_neg}",
        f"lineCap_big={line_cap_big}",
        f"lineJoin_neg={line_join_neg}",
        f"alpha_over={alpha_over}",
        f"nsAlpha_neg={ns_alpha_neg}",
        f"alpha_nan={alpha_nan}",
        f"flatness_inf={flatness_inf}",
        f"smoothness_neg={smoothness_neg}",
        f"opm_neg={opm_neg}",
        f"lineWidth_nan={line_width_nan}",
        f"lineWidth_inf={line_width_inf}",
    ]


_PROJECTORS = {
    "defaults": _py_defaults,
    "clone": _py_clone,
    "setters": _py_setters,
}


@requires_oracle
@pytest.mark.parametrize("mode", ["defaults", "clone", "setters"], ids=["def", "clone", "set"])
def test_graphics_state_object_matches_pdfbox(mode: str) -> None:
    java_lines = run_probe_text(_PROBE, mode).splitlines()
    py_lines = _PROJECTORS[mode]()
    assert py_lines == java_lines
