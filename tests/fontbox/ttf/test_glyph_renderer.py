"""Tests for :class:`pypdfbox.fontbox.ttf.glyph_renderer.GlyphRenderer`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript
from pypdfbox.fontbox.ttf.glyph_renderer import (
    GlyphRenderer,
    _mid_int,
)
from pypdfbox.fontbox.ttf.point import Point


def _make_triangle() -> GlyfSimpleDescript:
    d = GlyfSimpleDescript()
    d._contour_count = 1
    d._end_pts_of_contours = [2]
    d._flags = [
        GlyfDescript.ON_CURVE,
        GlyfDescript.ON_CURVE,
        GlyfDescript.ON_CURVE,
    ]
    d._x_coordinates = [0, 10, 5]
    d._y_coordinates = [0, 0, 10]
    d._point_count = 3
    return d


def test_render_simple_triangle() -> None:
    renderer = GlyphRenderer(_make_triangle())
    pen = renderer.get_path()
    ops = [op for (op, _args) in pen.value]
    # Three on-curve points -> moveTo, lineTo, lineTo, lineTo, closePath.
    assert ops[0] == "moveTo"
    assert ops[-1] == "closePath"
    assert ops.count("lineTo") == 3


def test_render_zero_point_glyph_emits_nothing() -> None:
    d = GlyfSimpleDescript()
    pen = GlyphRenderer(d).get_path()
    assert pen.value == []


def test_describe_marks_end_of_contour() -> None:
    d = _make_triangle()
    points = GlyphRenderer.describe(d)
    assert len(points) == 3
    assert points[0].end_of_contour is False
    assert points[1].end_of_contour is False
    assert points[2].end_of_contour is True
    # All flagged on-curve.
    for p in points:
        assert p.on_curve is True


def test_render_with_off_curve_start() -> None:
    """One contour starting off-curve, ending on-curve.

    Upstream prepends the last (on-curve) point to the contour list and
    walks from there (GlyphRenderer.java lines 114-118). The recorded
    path should still start with ``moveTo`` and include at least one
    ``qCurveTo``.
    """
    d = GlyfSimpleDescript()
    d._contour_count = 1
    d._end_pts_of_contours = [2]
    d._flags = [
        0,  # off-curve
        GlyfDescript.ON_CURVE,
        GlyfDescript.ON_CURVE,
    ]
    d._x_coordinates = [0, 10, 20]
    d._y_coordinates = [0, 10, 0]
    d._point_count = 3
    pen = GlyphRenderer(d).get_path()
    ops = [op for (op, _args) in pen.value]
    assert ops[0] == "moveTo"
    assert "qCurveTo" in ops
    assert ops[-1] == "closePath"


def test_render_both_endpoints_off_curve() -> None:
    """Off-curve start *and* end -> implicit midpoint synthesised."""
    d = GlyfSimpleDescript()
    d._contour_count = 1
    d._end_pts_of_contours = [2]
    d._flags = [0, GlyfDescript.ON_CURVE, 0]
    d._x_coordinates = [0, 10, 20]
    d._y_coordinates = [0, 10, 0]
    d._point_count = 3
    pen = GlyphRenderer(d).get_path()
    ops = [op for (op, _args) in pen.value]
    assert ops[0] == "moveTo"
    assert "qCurveTo" in ops
    assert ops[-1] == "closePath"


def test_mid_int_truncates_toward_zero_like_java() -> None:
    # Java integer division truncates toward zero, so the midpoint of
    # (-1, 0) is -1 + (0 - -1) / 2 = -1 + 0 (truncated) = -1, not -1 + 0
    # (Python floor would give the same here, but the difference shows
    # on negative diffs).
    assert _mid_int(0, 10) == 5
    assert _mid_int(10, 0) == 5  # 10 + (0-10)/2 = 10 + -5 = 5
    assert _mid_int(0, -3) == -1  # 0 + int(-3/2) = 0 + -1 = -1
    assert _mid_int(0, 3) == 1
    assert _mid_int(5, 5) == 5


def test_midpoint_is_on_curve() -> None:
    p = GlyphRenderer.mid_value(
        Point(0, 0, on_curve=False), Point(10, 20, on_curve=False)
    )
    assert p.x == 5
    assert p.y == 10
    assert p.on_curve is True
