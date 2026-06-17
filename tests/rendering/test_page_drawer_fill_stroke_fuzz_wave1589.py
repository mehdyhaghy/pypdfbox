"""Fuzz / parity tests for PageDrawer path fill + stroke geometry — wave 1589.

Exercises the winding-rule selection (``f``/``F``/``f*``/``B``/``B*``/``b``/
``b*`` → non-zero vs even-odd reaching the rasteriser), the stroke-parameter
mapping pulled from the graphics state (line width scaled by the CTM with
PDFBox's 0.25-device-pixel floor, line cap / join enum mapping, miter limit,
dash array + phase scaling), the stroke-vs-fill colour source, and the empty
-path no-op.

The rasteriser internals (aggdraw / skia) are out of scope — these tests
record the *parameters* handed to the raster backend by monkeypatching the
``aggdraw.Pen`` / ``aggdraw.Brush`` factories and the ``Draw.path`` sink, then
assert on what reached them.

Upstream reference: Apache PDFBox 3.0.x
``org.apache.pdfbox.rendering.PageDrawer`` (``fillPath`` / ``strokePath`` /
``fillAndStrokePath`` / ``getStroke`` / ``getDashArray`` / ``isAllZeroDash``)
and ``PDFStreamEngine.transformWidth``.
"""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import (
    PDFRenderer,
)
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering import pdf_renderer as pr
from pypdfbox.rendering.page_drawer import PageDrawer

# Path2D winding-rule constants (java.awt.geom.Path2D).
WIND_EVEN_ODD = 0
WIND_NON_ZERO = 1


# ---------------------------------------------------------------------------
# Recording harness
# ---------------------------------------------------------------------------


class _Recorder:
    """Captures every Pen / Brush built and every ``path`` call made while a
    paint helper runs."""

    def __init__(self) -> None:
        self.pens: list[Any] = []
        self.brushes: list[Any] = []
        # Colour argument (first positional) handed to the factory.
        self.pen_colors: list[Any] = []
        self.brush_colors: list[Any] = []
        # Each path call: (pen, brush, even_odd)
        self.path_calls: list[tuple[Any, Any, bool]] = []


def _install_recorder(
    monkeypatch: pytest.MonkeyPatch, rec: _Recorder | None = None
) -> _Recorder:
    if rec is None:
        rec = _Recorder()
    real_pen = aggdraw.Pen
    real_brush = aggdraw.Brush

    def pen_factory(color: Any, *args: Any, **kwargs: Any) -> Any:
        pen = real_pen(color, *args, **kwargs)
        rec.pens.append(pen)
        rec.pen_colors.append(color)
        return pen

    def brush_factory(color: Any, *args: Any, **kwargs: Any) -> Any:
        brush = real_brush(color, *args, **kwargs)
        rec.brushes.append(brush)
        rec.brush_colors.append(color)
        return brush

    monkeypatch.setattr(pr.aggdraw, "Pen", pen_factory)
    monkeypatch.setattr(pr.aggdraw, "Brush", brush_factory)

    return rec


def _make_renderer(monkeypatch: pytest.MonkeyPatch, rec: _Recorder) -> PDFRenderer:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    doc.add_page(page)
    renderer = PDFRenderer(doc)

    renderer._gs_stack = [pr._GState()]

    image = Image.new("RGB", (100, 100), (255, 255, 255))
    renderer._image = image
    draw = aggdraw.Draw(image)
    renderer._draw = draw

    # Record what reaches the path sink so we can read the even-odd flag.
    real_path = draw.path

    def recording_path(path: Any, pen: Any = None, brush: Any = None,
                       *, even_odd: bool = False) -> Any:
        rec.path_calls.append((pen, brush, even_odd))
        return real_path(path, pen, brush, even_odd=even_odd)

    monkeypatch.setattr(draw, "path", recording_path)
    return renderer


def _square(renderer: PDFRenderer) -> None:
    """Populate ``_subpaths`` with a simple closed square."""
    renderer._subpaths = [[
        ("M", 10.0, 10.0),
        ("L", 90.0, 10.0),
        ("L", 90.0, 90.0),
        ("L", 10.0, 90.0),
        ("Z",),
    ]]


# ---------------------------------------------------------------------------
# Winding-rule selection: f / F / f* / B / B* / b / b*
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "winding_rule, expect_even_odd",
    [
        (WIND_NON_ZERO, False),  # f / F / B / b
        (WIND_EVEN_ODD, True),   # f* / B* / b*
    ],
    ids=["nonzero", "evenodd"],
)
def test_fill_path_winding_reaches_rasteriser(
    monkeypatch: pytest.MonkeyPatch, winding_rule: int, expect_even_odd: bool
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    _square(renderer)
    renderer._draw_via_aggdraw(stroke=False, fill=True, even_odd=expect_even_odd)
    assert rec.path_calls, "fill must reach the path sink"
    # The even-odd flag the rasteriser receives must match the winding rule.
    assert rec.path_calls[-1][2] is expect_even_odd


def test_fill_path_helper_maps_winding_to_even_odd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # PageDrawer.fill_path: WIND_EVEN_ODD(0) -> even_odd=True, else False.
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    drawer = PageDrawer.__new__(PageDrawer)
    drawer._renderer = renderer
    drawer._line_path = []

    _square(renderer)
    drawer.fill_path(WIND_EVEN_ODD)
    assert rec.path_calls[-1][2] is True

    rec.path_calls.clear()
    _square(renderer)
    drawer.fill_path(WIND_NON_ZERO)
    assert rec.path_calls[-1][2] is False


def test_fill_and_stroke_winding_only_affects_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # B* must fill even-odd; the stroke band itself has no winding rule.
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    _square(renderer)
    renderer._draw_via_aggdraw(stroke=True, fill=True, even_odd=True)
    # First path call is the even-odd fill; a later call is the stroke.
    fill_call = next(c for c in rec.path_calls if c[1] is not None)
    assert fill_call[2] is True


def test_stroke_path_fill_rule_is_irrelevant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # strokePath has no winding rule; the stroke path call carries a pen.
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    _square(renderer)
    renderer._stroke_via_aggdraw()
    stroke_calls = [c for c in rec.path_calls if c[0] is not None]
    assert stroke_calls, "stroke must emit a pen path call"
    assert stroke_calls[-1][1] is None  # no brush on a pure stroke


# ---------------------------------------------------------------------------
# Line width transform + 0.25 device-pixel floor (PDFBox getStroke)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line_width, scale, expected",
    [
        (0.0, 1.0, 0.25),    # zero width -> 0.25 floor
        (0.1, 1.0, 0.25),    # sub-floor width -> 0.25 floor
        (1.0, 1.0, 1.0),     # exact width passes through
        (2.0, 1.0, 2.0),
        (1.0, 3.0, 3.0),     # CTM uniform scale 3 -> 3.0
        (0.5, 2.0, 1.0),     # 0.5 * 2 = 1.0
        (0.05, 4.0, 0.25),   # 0.05 * 4 = 0.2 < 0.25 -> floored
        (10.0, 0.5, 5.0),    # downscale
    ],
    ids=["zero", "subfloor", "unit", "double", "ctm3",
         "halfx2", "tiny_floored", "down"],
)
def test_stroke_width_ctm_scaled_with_quarter_floor(
    monkeypatch: pytest.MonkeyPatch,
    line_width: float, scale: float, expected: float,
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.line_width = line_width
    renderer._gs.ctm = (scale, 0.0, 0.0, scale, 0.0, 0.0)
    _square(renderer)
    renderer._stroke_via_aggdraw()
    assert rec.pens, "stroke must build a pen"
    assert rec.pens[-1].width == pytest.approx(expected)


def test_stroke_width_anisotropic_ctm_uses_transform_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # PDFBox transformWidth: sqrt(((a+c)^2 + (b+d)^2)/2). For cm 3 0 0 1 ->
    # x=3, y=1 -> sqrt((9+1)/2) = sqrt(5). NOT the geometric mean sqrt(3).
    import math

    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.line_width = 1.0
    renderer._gs.ctm = (3.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    _square(renderer)
    renderer._stroke_via_aggdraw()
    assert rec.pens[-1].width == pytest.approx(math.sqrt(5.0))


def test_transform_width_scale_formula() -> None:
    import math

    # Identity -> 1.
    assert PDFRenderer._transform_width_scale(
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    ) == pytest.approx(1.0)
    # Uniform scale s -> s (== sqrt(|det|)).
    assert PDFRenderer._transform_width_scale(
        (4.0, 0.0, 0.0, 4.0, 0.0, 0.0)
    ) == pytest.approx(4.0)
    # Degenerate (all-zero columns) clamps to 1.0, never zero.
    assert PDFRenderer._transform_width_scale(
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    ) == pytest.approx(1.0)
    # Shear-only CTM: a=1,b=0,c=1,d=1 -> x=2,y=1 -> sqrt(5/2).
    assert PDFRenderer._transform_width_scale(
        (1.0, 0.0, 1.0, 1.0, 0.0, 0.0)
    ) == pytest.approx(math.sqrt(2.5))


# ---------------------------------------------------------------------------
# Line cap / join enum mapping (PDF 0/1/2 reach the pen unchanged)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cap", [0, 1, 2], ids=["butt", "round", "square"])
def test_line_cap_maps_to_pen(
    monkeypatch: pytest.MonkeyPatch, cap: int
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.line_cap = cap
    _square(renderer)
    renderer._stroke_via_aggdraw()
    assert rec.pens[-1].line_cap == cap


@pytest.mark.parametrize("join", [0, 1, 2], ids=["miter", "round", "bevel"])
def test_line_join_maps_to_pen(
    monkeypatch: pytest.MonkeyPatch, join: int
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.line_join = join
    _square(renderer)
    renderer._stroke_via_aggdraw()
    assert rec.pens[-1].line_join == join


def test_op_line_cap_rejects_out_of_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.cos import COSInteger

    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    renderer._gs.line_cap = 1
    renderer._op_line_cap(None, [COSInteger.get(5)])  # 5 is illegal
    assert renderer._gs.line_cap == 1  # unchanged


# ---------------------------------------------------------------------------
# Miter limit: PDFBox getStroke resets a value < 1 to the spec default of 10
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "miter, expected",
    [
        (10.0, 10.0),
        (4.0, 4.0),
        (1.0, 1.0),
        (0.5, 10.0),   # < 1 illegal -> reset to default 10
        (0.0, 10.0),   # would be stored as default anyway via op-guard
    ],
    ids=["ten", "four", "one", "half_reset", "zero_reset"],
)
def test_miter_limit_below_one_resets_to_ten(
    monkeypatch: pytest.MonkeyPatch, miter: float, expected: float
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.miter_limit = miter
    _square(renderer)
    renderer._stroke_via_aggdraw()
    assert rec.pens[-1].miter_limit == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Dash array + phase mapping
# ---------------------------------------------------------------------------


def test_empty_dash_is_solid(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.dash_pattern = None  # solid line
    _square(renderer)
    renderer._stroke_via_aggdraw()
    assert rec.pens[-1].dash is None


def test_dash_intervals_and_phase_scaled_by_ctm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.dash_pattern = ((3.0, 2.0), 1.0)
    renderer._gs.ctm = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)  # scale 2
    _square(renderer)
    renderer._stroke_via_aggdraw()
    intervals, phase = rec.pens[-1].dash
    assert intervals == pytest.approx([6.0, 4.0])
    assert phase == pytest.approx(2.0)


def test_dash_phase_preserved_at_identity_ctm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.dash_pattern = ((4.0, 4.0), 2.5)
    _square(renderer)
    renderer._stroke_via_aggdraw()
    intervals, phase = rec.pens[-1].dash
    assert intervals == pytest.approx([4.0, 4.0])
    assert phase == pytest.approx(2.5)


def test_all_zero_dash_paints_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # PDFBOX-5168 / isAllZeroDash: an all-zero dash array makes the stroke
    # invisible — no pen is built, no path call is emitted.
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.dash_pattern = ((0.0, 0.0), 0.0)
    _square(renderer)
    renderer._stroke_via_aggdraw()
    assert not rec.pens, "all-zero dash must not build a stroke pen"
    assert not rec.path_calls


def test_single_element_dash_scaled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.dash_pattern = ((5.0,), 0.0)
    renderer._gs.ctm = (3.0, 0.0, 0.0, 3.0, 0.0, 0.0)
    _square(renderer)
    renderer._stroke_via_aggdraw()
    intervals, _phase = rec.pens[-1].dash
    assert intervals == pytest.approx([15.0])


# ---------------------------------------------------------------------------
# Stroke colour vs fill colour source
# ---------------------------------------------------------------------------


def test_stroke_uses_stroke_rgb(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.stroke_rgb = (200, 50, 25)
    renderer._gs.fill_rgb = (1, 2, 3)
    _square(renderer)
    renderer._stroke_via_aggdraw()
    # Pen colour derives from stroke_rgb (after transfer-fn identity).
    assert tuple(rec.pen_colors[-1]) == (200, 50, 25)


def test_fill_uses_fill_rgb(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.fill_rgb = (10, 220, 30)
    renderer._gs.stroke_rgb = (9, 9, 9)
    _square(renderer)
    renderer._draw_via_aggdraw(stroke=False, fill=True, even_odd=False)
    assert tuple(rec.brush_colors[-1]) == (10, 220, 30)


def test_fill_and_stroke_use_distinct_colours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._gs.fill_rgb = (255, 0, 0)
    renderer._gs.stroke_rgb = (0, 0, 255)
    _square(renderer)
    renderer._draw_via_aggdraw(stroke=True, fill=True, even_odd=False)
    assert tuple(rec.brush_colors[-1]) == (255, 0, 0)
    assert tuple(rec.pen_colors[-1]) == (0, 0, 255)


# ---------------------------------------------------------------------------
# Empty path -> no-op
# ---------------------------------------------------------------------------


def test_empty_subpaths_no_op_stroke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._subpaths = []
    renderer._stroke_via_aggdraw()
    assert not rec.pens
    assert not rec.path_calls


def test_subpath_with_no_segments_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    # A subpath with only a close (no move/line/curve) yields no segments.
    renderer._subpaths = [[("Z",)]]
    renderer._draw_via_aggdraw(stroke=True, fill=True, even_odd=False)
    assert not rec.pens
    assert not rec.brushes


def test_paint_empty_path_applies_pending_clip_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._subpaths = []
    # _paint with empty subpaths is a no-op (just clip handling), no pen.
    renderer._paint(stroke=True, fill=False, even_odd=False)
    assert not rec.pens
    assert not rec.path_calls


# ---------------------------------------------------------------------------
# Curve segments survive into the rasterised stroke path
# ---------------------------------------------------------------------------


def test_curve_segments_stroked(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder()
    renderer = _make_renderer(monkeypatch, rec)
    _install_recorder(monkeypatch, rec)
    renderer._subpaths = [[
        ("M", 10.0, 10.0),
        ("C", 20.0, 80.0, 80.0, 80.0, 90.0, 10.0),
    ]]
    renderer._stroke_via_aggdraw()
    assert rec.pens, "curve-only path must still stroke"
