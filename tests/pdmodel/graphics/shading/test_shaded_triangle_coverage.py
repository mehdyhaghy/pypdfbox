"""Coverage tests for
:mod:`pypdfbox.pdmodel.graphics.shading.shaded_triangle`.

Drives ``calc_deg`` (1/2/3-vertex cases), the alternate
``_line`` branch (``corner1 == corner2 != corner0``), ``contains`` for
degree-1, degree-2 (line) and degree-3 (full triangle) cases,
``calc_color`` for the same three branches plus the zero-area
fallback, and the ``to_string`` / ``__repr__`` formatting.
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.shading.line import Line
from pypdfbox.pdmodel.graphics.shading.shaded_triangle import ShadedTriangle


# ---------------------------------------------------------------------------
# Degree classifier
# ---------------------------------------------------------------------------
def test_calc_deg_one_when_all_three_corners_coincide() -> None:
    deg = ShadedTriangle.calc_deg([(1.0, 1.0), (1.0, 1.0), (1.0, 1.0)])
    assert deg == 1


def test_calc_deg_two_when_two_corners_coincide() -> None:
    deg = ShadedTriangle.calc_deg([(0.0, 0.0), (5.0, 5.0), (5.0, 5.0)])
    assert deg == 2


def test_calc_deg_three_for_distinct_corners() -> None:
    deg = ShadedTriangle.calc_deg([(0.0, 0.0), (5.0, 0.0), (0.0, 5.0)])
    assert deg == 3


# ---------------------------------------------------------------------------
# Constructor branches
# ---------------------------------------------------------------------------
def test_degenerate_corner1_corner2_uses_zero_two_line_branch() -> None:
    """corner1 == corner2 but corner0 distinct → uses the (corner0,corner2)
    line branch (lines 32-33 in the source).
    """
    tri = ShadedTriangle(
        [(0.0, 0.0), (5.0, 5.0), (5.0, 5.0)],
        [[0.1], [0.5], [0.9]],
    )
    assert tri.get_deg() == 2
    line = tri.get_line()
    assert isinstance(line, Line)
    # Endpoints should be the rounded corners (corner0, corner2).
    assert (0, 0) in line.line_points
    assert (5, 5) in line.line_points


def test_degenerate_corner0_corner1_uses_one_two_line_branch() -> None:
    """corner1 != corner2 but corner0 == corner1 → uses the (corner1,corner2)
    line branch (lines 35-37 in the source).
    """
    tri = ShadedTriangle(
        [(0.0, 0.0), (0.0, 0.0), (5.0, 5.0)],
        [[0.0], [0.5], [1.0]],
    )
    assert tri.get_deg() == 2
    line = tri.get_line()
    assert isinstance(line, Line)
    assert (0, 0) in line.line_points
    assert (5, 5) in line.line_points


def test_non_degenerate_triangle_has_no_line() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (5.0, 0.0), (0.0, 5.0)],
        [[0.0], [0.5], [1.0]],
    )
    assert tri.get_line() is None
    assert tri.get_deg() == 3


# ---------------------------------------------------------------------------
# contains
# ---------------------------------------------------------------------------
def test_contains_single_point_degenerate_returns_true_on_match() -> None:
    tri = ShadedTriangle(
        [(3.0, 4.0), (3.0, 4.0), (3.0, 4.0)],
        [[0.0], [0.0], [0.0]],
    )
    assert tri.contains((3.0, 4.0)) is True
    assert tri.contains((9.0, 9.0)) is False


def test_contains_line_degenerate_returns_true_on_rasterised_point() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (5.0, 5.0), (5.0, 5.0)],
        [[0.0], [0.5], [1.0]],
    )
    # (3,3) lies on the diagonal — Bresenham rasterised.
    assert tri.contains((3.0, 3.0)) is True
    # (3,4) lies just off — not in the rasterised set.
    assert tri.contains((3.0, 4.0)) is False


def test_contains_returns_true_for_centre_of_triangle() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)],
        [[0.0], [0.5], [1.0]],
    )
    assert tri.contains((1.0, 1.0)) is True


def test_contains_returns_false_for_point_outside_triangle() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)],
        [[0.0], [0.5], [1.0]],
    )
    assert tri.contains((10.0, 10.0)) is False


def test_contains_returns_false_when_one_edge_sign_flips() -> None:
    """Ensure both edge-sign-rejection branches (the early ``return False`` on
    pv0 and pv1) are exercised in different configurations.
    """
    tri = ShadedTriangle(
        [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)],
        [[0.0], [0.5], [1.0]],
    )
    assert tri.contains((-1.0, 5.0)) is False
    assert tri.contains((5.0, -1.0)) is False


# ---------------------------------------------------------------------------
# calc_color
# ---------------------------------------------------------------------------
def test_calc_color_single_point_averages_three_corner_colours() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
        [[0.0], [1.0], [2.0]],
    )
    assert tri.calc_color((0.0, 0.0)) == [1.0]


def test_calc_color_line_degenerate_delegates_to_line_interpolation() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 0.0)],
        [[0.0], [1.0], [1.0]],
    )
    # Midpoint of the rasterised segment.
    assert tri.calc_color((5.0, 0.0))[0] == 0.5


def test_calc_color_zero_area_returns_first_corner_colour() -> None:
    """Three distinct but collinear points → degree==3, area==0 — code
    returns ``self.color[0]`` (line 115 in source).
    """
    tri = ShadedTriangle(
        [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)],
        [[0.25], [0.5], [0.75]],
    )
    assert tri.get_deg() == 3
    assert tri.calc_color((1.0, 1.0)) == [0.25]


def test_calc_color_interpolates_via_barycentric_weights_for_full_triangle() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)],
        [[0.0], [1.0], [0.0]],
    )
    # Centroid → average colour.
    centroid = (10 / 3, 10 / 3)
    assert round(tri.calc_color(centroid)[0], 6) == round(1 / 3, 6)


# ---------------------------------------------------------------------------
# Boundary helpers + repr
# ---------------------------------------------------------------------------
def test_get_boundary_returns_axis_aligned_bounding_box() -> None:
    tri = ShadedTriangle(
        [(-1.4, 2.6), (5.0, 1.0), (3.0, -2.4)],
        [[0.0], [0.0], [0.0]],
    )
    # Rounding follows Python banker's rounding → -1.4 → -1, 2.6 → 3, etc.
    assert tri.get_boundary() == [-1, 5, -2, 3]


def test_overlaps_static_helper_below_threshold() -> None:
    assert ShadedTriangle.overlaps((1.0, 1.0), (1.0005, 1.0005)) is True


def test_overlaps_static_helper_above_threshold() -> None:
    assert ShadedTriangle.overlaps((1.0, 1.0), (1.5, 1.0)) is False


def test_edge_equation_value_is_zero_on_line() -> None:
    assert ShadedTriangle.edge_equation_value((1, 1), (0, 0), (2, 2)) == 0


def test_get_area_returns_half_cross_product_magnitude() -> None:
    assert ShadedTriangle.get_area((0, 0), (4, 0), (0, 6)) == 12.0


def test_to_string_and_repr_emit_pdfbox_style_format() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (5.0, 0.0), (0.0, 5.0)],
        [[0.0], [0.5], [1.0]],
    )
    text = tri.to_string()
    assert "Point2D.Double[0.0, 0.0]" in text
    assert "Point2D.Double[5.0, 0.0]" in text
    assert "Point2D.Double[0.0, 5.0]" in text
    assert repr(tri) == text
