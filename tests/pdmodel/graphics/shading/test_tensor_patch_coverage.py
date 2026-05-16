"""Coverage tests for :mod:`pypdfbox.pdmodel.graphics.shading.tensor_patch`.

Targets the level-reduction branches inside :meth:`TensorPatch.calc_level`,
the ``is_on_same_side_cc`` / ``is_on_same_side_dd`` helpers, and the
``get_flag*_edge`` accessors that the wave 1280 baseline did not exercise.
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.shading.tensor_patch import TensorPatch


# ----------------------------------------------------------------------
# Control-point fixtures
# ----------------------------------------------------------------------
def _flat_patch(width: float, height: float) -> TensorPatch:
    """Build a tensor patch whose outer 12 control points lie on the
    rectangle (0,0)-(width,height), so the cc and dd edges are exactly
    straight lines (``is_edge_a_line`` returns True).

    The 4 interior control points (indices 12-15) are placed inside
    the rectangle so neither ``is_on_same_side_cc`` nor
    ``is_on_same_side_dd`` returns True — that drives the length-based
    level-reduction branches.
    """
    # Upstream Tensor-patch ordering: 12 boundary points (top, right,
    # bottom, left edges) followed by 4 interior tensor control points.
    pts = [
        # Top edge L->R: 0..3 (y=0)
        (0.0, 0.0), (width / 3, 0.0), (2 * width / 3, 0.0), (width, 0.0),
        # Right edge T->B: 4,5 (x=width)
        (width, height / 3), (width, 2 * height / 3),
        # Bottom-right corner index 6
        (width, height),
        # Bottom edge R->L: 7,8 (y=height)
        (2 * width / 3, height), (width / 3, height),
        # Bottom-left corner index 9
        (0.0, height),
        # Left edge B->T: 10,11 (x=0)
        (0.0, 2 * height / 3), (0.0, height / 3),
        # Interior tensor control points 12..15
        (width / 3, height / 3),
        (2 * width / 3, height / 3),
        (2 * width / 3, 2 * height / 3),
        (width / 3, 2 * height / 3),
    ]
    colors = [[0.0], [1.0], [0.0], [1.0]]
    return TensorPatch(pts, colors)


# ----------------------------------------------------------------------
# Level-reduction branches in calc_level
# ----------------------------------------------------------------------
def test_calc_level_short_edges_drop_both_levels_to_one() -> None:
    """Tiny flat patch (50x50) — both axis lengths <= 200, so the
    level for both axes drops to 1 (lines 64-65 + 86-87).
    """
    patch = _flat_patch(50.0, 50.0)
    assert patch.level == [1, 1]


def test_calc_level_medium_edges_drop_to_two() -> None:
    """Lengths in (200, 400] -> level 2 on each axis (lines 62-63 + 84-85)."""
    patch = _flat_patch(300.0, 300.0)
    assert patch.level == [2, 2]


def test_calc_level_long_edges_drop_to_three() -> None:
    """Lengths in (400, 800] -> level 3 on each axis (lines 60-61 + 82-83)."""
    patch = _flat_patch(500.0, 500.0)
    assert patch.level == [3, 3]


def test_calc_level_huge_edges_keep_level_four() -> None:
    """Lengths > 800 keep the default level 4 (the ``pass`` branches at
    58-59 and 80-81)."""
    patch = _flat_patch(900.0, 900.0)
    assert patch.level == [4, 4]


# ----------------------------------------------------------------------
# is_on_same_side_cc / dd predicates (lines 91-96 and 99-104)
# ----------------------------------------------------------------------
def test_is_on_same_side_cc_returns_true_for_point_outside_rectangle() -> None:
    patch = _flat_patch(100.0, 100.0)
    # cc compares signed distance from the two vertical edges; a point
    # to the right of both vertical edges yields positive product.
    assert patch.is_on_same_side_cc((200.0, 50.0)) is True


def test_is_on_same_side_cc_returns_false_for_interior_point() -> None:
    patch = _flat_patch(100.0, 100.0)
    # An interior point lies between the two vertical edges -> product
    # of edge-equation values is negative.
    assert patch.is_on_same_side_cc((50.0, 50.0)) is False


def test_is_on_same_side_dd_returns_true_for_point_above_both_edges() -> None:
    patch = _flat_patch(100.0, 100.0)
    # dd compares signed distance from the two horizontal edges; a point
    # above both yields positive product.
    assert patch.is_on_same_side_dd((50.0, -100.0)) is True


def test_is_on_same_side_dd_returns_false_for_interior_point() -> None:
    patch = _flat_patch(100.0, 100.0)
    assert patch.is_on_same_side_dd((50.0, 50.0)) is False


# ----------------------------------------------------------------------
# get_flag*_edge accessors (lines 111, 114, 117)
# ----------------------------------------------------------------------
def test_get_flag1_edge_returns_right_column_of_control_points() -> None:
    patch = _flat_patch(100.0, 100.0)
    edge = patch.get_flag1_edge()
    assert len(edge) == 4
    # The right column (j=3) of the reshaped 4x4 grid.
    assert edge == [patch.control_points[i][3] for i in range(4)]


def test_get_flag2_edge_returns_bottom_row_reversed() -> None:
    patch = _flat_patch(100.0, 100.0)
    edge = patch.get_flag2_edge()
    assert len(edge) == 4
    assert edge == [patch.control_points[3][3 - i] for i in range(4)]


def test_get_flag3_edge_returns_left_column_reversed() -> None:
    patch = _flat_patch(100.0, 100.0)
    edge = patch.get_flag3_edge()
    assert len(edge) == 4
    assert edge == [patch.control_points[3 - i][0] for i in range(4)]


# ----------------------------------------------------------------------
# Same-side-true short-circuits the length check (lines 53-54 and 75-76)
# ----------------------------------------------------------------------
def test_calc_level_with_interior_control_outside_rectangle() -> None:
    """When an interior tensor control point lies outside the patch on
    both vertical edges, the ``is_on_same_side_cc`` short-circuit keeps
    the axis-0 level at the default 4 even on a small patch.
    """
    pts = [
        (0.0, 0.0), (30.0, 0.0), (60.0, 0.0), (100.0, 0.0),
        (100.0, 30.0), (100.0, 60.0),
        (100.0, 100.0),
        (60.0, 100.0), (30.0, 100.0),
        (0.0, 100.0),
        (0.0, 60.0), (0.0, 30.0),
        # Interior point [1][1] lies right of both vertical edges
        # (x > 100) -> is_on_same_side_cc returns True -> axis-0
        # level stays at 4 (the ``pass`` at line 54).
        (200.0, 30.0),
        (60.0, 30.0),
        (60.0, 60.0),
        (30.0, 60.0),
    ]
    colors = [[0.0], [1.0], [0.0], [1.0]]
    patch = TensorPatch(pts, colors)
    assert patch.level[0] == 4


def test_calc_level_with_interior_control_outside_horizontal_edges() -> None:
    """When an interior tensor control point lies outside both
    horizontal edges, the ``is_on_same_side_dd`` short-circuit keeps the
    axis-1 level at the default 4 (the ``pass`` at line 76).
    """
    pts = [
        (0.0, 0.0), (30.0, 0.0), (60.0, 0.0), (100.0, 0.0),
        (100.0, 30.0), (100.0, 60.0),
        (100.0, 100.0),
        (60.0, 100.0), (30.0, 100.0),
        (0.0, 100.0),
        (0.0, 60.0), (0.0, 30.0),
        # Interior point [1][1] sits below y=0 -> is_on_same_side_dd
        # returns True -> axis-1 level stays at 4.
        (30.0, -200.0),
        (60.0, 30.0),
        (60.0, 60.0),
        (30.0, 60.0),
    ]
    colors = [[0.0], [1.0], [0.0], [1.0]]
    patch = TensorPatch(pts, colors)
    assert patch.level[1] == 4
