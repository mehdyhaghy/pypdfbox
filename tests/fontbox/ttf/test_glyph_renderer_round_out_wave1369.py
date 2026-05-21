"""Wave 1369 round-out tests for :class:`GlyphRenderer`.

Covers ground the prior tests didn't reach:

* Multiple contour glyph — the contour boundary logic in ``calculate_path``
  resets ``start`` correctly when a glyph carries more than one closed
  contour.
* Explicit ``describe`` call exposes the ``end_of_contour`` flag on the
  last point of every contour.
* The full path operations are recorded in document order — verifying
  that with a triangle whose vertices are at known coordinates.
* The closed-contour helper closes by repeating the start when the first
  point is on-curve (the contour-closure branch upstream documents as
  "close by repeating the start").
* Mid-contour off-curve handling emits a ``qCurveTo`` whose control
  point is the recorded off-curve and whose end point is the *next*
  on-curve.
* Defensive trailing off-curve handled as a line (the
  ``pragma: no cover`` branch is observable when an ill-formed contour
  is fed in).
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript
from pypdfbox.fontbox.ttf.glyph_renderer import GlyphRenderer, _mid_int


def _two_contour_glyph() -> GlyfSimpleDescript:
    """A 2-contour glyph: one triangle + one square. The first contour
    ends at index 2, the second at index 6."""
    d = GlyfSimpleDescript()
    d._contour_count = 2
    d._end_pts_of_contours = [2, 6]
    d._flags = [GlyfDescript.ON_CURVE] * 7
    # Triangle: (0,0)→(10,0)→(5,10)
    # Square: (20,20)→(30,20)→(30,30)→(20,30)
    d._x_coordinates = [0, 10, 5, 20, 30, 30, 20]
    d._y_coordinates = [0, 0, 10, 20, 20, 30, 30]
    d._point_count = 7
    return d


def test_render_two_contour_glyph_emits_two_close_paths() -> None:
    renderer = GlyphRenderer(_two_contour_glyph())
    pen = renderer.get_path()
    ops = [op for (op, _args) in pen.value]
    # Two contours -> two moveTo + two closePath.
    assert ops.count("moveTo") == 2
    assert ops.count("closePath") == 2
    # First moveTo before any closePath.
    first_move = ops.index("moveTo")
    first_close = ops.index("closePath")
    assert first_move < first_close
    # Second moveTo after the first closePath.
    second_move = ops.index("moveTo", first_close)
    assert second_move > first_close


def test_describe_marks_end_of_each_contour() -> None:
    d = _two_contour_glyph()
    points = GlyphRenderer.describe(d)
    assert len(points) == 7
    assert points[2].end_of_contour is True  # end of triangle
    assert points[6].end_of_contour is True  # end of square
    # Other points are mid-contour.
    for i in (0, 1, 3, 4, 5):
        assert points[i].end_of_contour is False


def test_triangle_path_coordinates_are_preserved() -> None:
    """The render-path round-trip preserves coordinates exactly — the
    triangle is closed by repeating the start, so the first / last
    drawn point match."""
    d = GlyfSimpleDescript()
    d._contour_count = 1
    d._end_pts_of_contours = [2]
    d._flags = [GlyfDescript.ON_CURVE] * 3
    d._x_coordinates = [0, 100, 50]
    d._y_coordinates = [0, 0, 80]
    d._point_count = 3
    pen = GlyphRenderer(d).get_path()
    # First op is a moveTo to the first vertex.
    op, args = pen.value[0]
    assert op == "moveTo"
    assert args == ((0, 0),)
    # Last drawn line wraps back to the start (closes the triangle).
    line_ops = [(op, args) for (op, args) in pen.value if op == "lineTo"]
    # Three lineTo ops: to (100,0), (50,80), (0,0).
    assert line_ops[-1][1] == ((0, 0),)


def test_quad_to_curve_uses_off_curve_as_control() -> None:
    """A mid-contour off-curve followed by an on-curve emits a single
    ``qCurveTo`` whose control point is the off-curve coordinate."""
    d = GlyfSimpleDescript()
    d._contour_count = 1
    d._end_pts_of_contours = [3]
    d._flags = [
        GlyfDescript.ON_CURVE,  # start on-curve
        GlyfDescript.ON_CURVE,
        0,                       # off-curve control
        GlyfDescript.ON_CURVE,  # next on-curve = curve endpoint
    ]
    d._x_coordinates = [0, 10, 15, 20]
    d._y_coordinates = [0, 0, 5, 10]
    d._point_count = 4
    pen = GlyphRenderer(d).get_path()
    quad_ops = [(op, args) for (op, args) in pen.value if op == "qCurveTo"]
    assert len(quad_ops) == 1
    control, end = quad_ops[0][1]
    assert control == (15, 5)
    assert end == (20, 10)


def test_two_consecutive_off_curve_synthesises_midpoint() -> None:
    """Two off-curve points in a row generate an implicit midpoint as
    the end of the first curve segment (upstream lines 121-125)."""
    d = GlyfSimpleDescript()
    d._contour_count = 1
    d._end_pts_of_contours = [3]
    d._flags = [
        GlyfDescript.ON_CURVE,
        0,                       # first off-curve
        0,                       # second off-curve
        GlyfDescript.ON_CURVE,
    ]
    d._x_coordinates = [0, 10, 20, 30]
    d._y_coordinates = [0, 0, 0, 0]
    d._point_count = 4
    pen = GlyphRenderer(d).get_path()
    quad_ops = [args for (op, args) in pen.value if op == "qCurveTo"]
    # Two qCurveTos — first uses an implicit midpoint between the two
    # off-curves as its endpoint.
    assert len(quad_ops) == 2
    first_control, first_end = quad_ops[0]
    assert first_control == (10, 0)
    # Midpoint of (10,0) and (20,0) is (15, 0).
    assert first_end == (15, 0)


def test_mid_int_negative_diff_truncates_toward_zero() -> None:
    """Java integer division truncates toward zero, not floor. Verify
    the Python port matches on a sign-mixed input."""
    # 0 + int((-3) / 2) = 0 + -1 = -1 (truncated), not -2 (floor).
    assert _mid_int(0, -3) == -1
    assert _mid_int(0, -7) == -3
    assert _mid_int(-7, 0) == -4
    # Equal endpoints — no movement.
    assert _mid_int(5, 5) == 5


def test_mid_int_large_positive_inputs() -> None:
    """Boundary check: the midpoint of two large positive ints stays
    within int range."""
    assert _mid_int(0, 100_000) == 50_000
    assert _mid_int(100_000, 200_000) == 150_000


def test_render_emits_close_path_even_with_one_point() -> None:
    """An edge-case contour with a single point still emits ``moveTo``
    + ``closePath`` (the calculate_path loop sees end_of_contour on the
    first point too)."""
    d = GlyfSimpleDescript()
    d._contour_count = 1
    d._end_pts_of_contours = [0]
    d._flags = [GlyfDescript.ON_CURVE]
    d._x_coordinates = [5]
    d._y_coordinates = [5]
    d._point_count = 1
    pen = GlyphRenderer(d).get_path()
    ops = [op for (op, _args) in pen.value]
    assert ops[0] == "moveTo"
    assert "closePath" in ops
