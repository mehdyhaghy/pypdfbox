"""Coverage tests for :mod:`pypdfbox.pdmodel.graphics.shading.patch`.

Drives the abstract ``get_flag*_edge`` accessors, the
``get_flag*_color`` helpers, geometry helpers (``get_len``,
``is_edge_a_line``, ``edge_equation_value``, ``overlaps``) and the
``get_shaded_triangles`` tessellation including both overlap-skip
branches.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.shading.patch import Patch, _CoordinateColorPair
from pypdfbox.pdmodel.graphics.shading.shaded_triangle import ShadedTriangle


class _ConcretePatch(Patch):
    """Minimal concrete subclass so we can exercise the base class itself."""

    def get_flag1_edge(self) -> list[tuple[float, float]]:
        return [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]

    def get_flag2_edge(self) -> list[tuple[float, float]]:
        return [(0.0, 1.0), (1.0, 1.0), (2.0, 1.0), (3.0, 1.0)]

    def get_flag3_edge(self) -> list[tuple[float, float]]:
        return [(0.0, 2.0), (1.0, 2.0), (2.0, 2.0), (3.0, 2.0)]


def _patch() -> _ConcretePatch:
    return _ConcretePatch([[0.0], [0.25], [0.5], [0.75]])


# ---------------------------------------------------------------------------
# Abstract get_flag*_edge — base class raises NotImplementedError
# ---------------------------------------------------------------------------
def test_base_get_flag1_edge_is_abstract() -> None:
    with pytest.raises(NotImplementedError, match="get_flag1_edge"):
        Patch([[0.0], [0.0], [0.0], [0.0]]).get_flag1_edge()


def test_base_get_flag2_edge_is_abstract() -> None:
    with pytest.raises(NotImplementedError, match="get_flag2_edge"):
        Patch([[0.0], [0.0], [0.0], [0.0]]).get_flag2_edge()


def test_base_get_flag3_edge_is_abstract() -> None:
    with pytest.raises(NotImplementedError, match="get_flag3_edge"):
        Patch([[0.0], [0.0], [0.0], [0.0]]).get_flag3_edge()


# ---------------------------------------------------------------------------
# Implicit colour pair helpers
# ---------------------------------------------------------------------------
def test_get_flag1_color_returns_corners_one_and_two() -> None:
    assert _patch().get_flag1_color() == [[0.25], [0.5]]


def test_get_flag2_color_returns_corners_two_and_three() -> None:
    assert _patch().get_flag2_color() == [[0.5], [0.75]]


def test_get_flag3_color_returns_corners_three_and_zero() -> None:
    assert _patch().get_flag3_color() == [[0.75], [0.0]]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def test_get_len_is_euclidean() -> None:
    assert Patch.get_len((0.0, 0.0), (3.0, 4.0)) == 5.0


def test_overlaps_below_threshold() -> None:
    assert Patch.overlaps((0.0, 0.0), (0.0005, 0.0005)) is True


def test_overlaps_above_threshold() -> None:
    assert Patch.overlaps((0.0, 0.0), (0.01, 0.0)) is False


def test_edge_equation_value_signs() -> None:
    # Point on the line returns 0.
    assert Patch.edge_equation_value((1.0, 1.0), (0.0, 0.0), (2.0, 2.0)) == 0.0
    # Point off the line returns non-zero with consistent sign.
    assert Patch.edge_equation_value((1.0, 0.0), (0.0, 0.0), (0.0, 1.0)) > 0


def test_is_edge_a_line_for_horizontal_edge() -> None:
    pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
    assert _patch().is_edge_a_line(pts) is True


def test_is_edge_a_line_for_vertical_edge() -> None:
    pts = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]
    assert _patch().is_edge_a_line(pts) is True


def test_is_edge_a_line_for_curved_edge() -> None:
    pts = [(0.0, 0.0), (1.0, 1.0), (2.0, -1.0), (3.0, 3.0)]
    assert _patch().is_edge_a_line(pts) is False


# ---------------------------------------------------------------------------
# get_shaded_triangles — happy path + both overlap-skip branches
# ---------------------------------------------------------------------------
def _ccp(coord: tuple[float, float], color: list[float]) -> _CoordinateColorPair:
    return _CoordinateColorPair(coord, color)


def test_get_shaded_triangles_emits_two_per_quad_for_distinct_corners() -> None:
    patch = _patch()
    grid = [
        [_ccp((0.0, 0.0), [0.0]), _ccp((1.0, 0.0), [0.25])],
        [_ccp((0.0, 1.0), [0.5]),  _ccp((1.0, 1.0), [0.75])],
    ]
    triangles = patch.get_shaded_triangles(grid)
    assert len(triangles) == 2
    assert all(isinstance(t, ShadedTriangle) for t in triangles)


def test_get_shaded_triangles_returns_empty_for_empty_grid() -> None:
    assert _patch().get_shaded_triangles([]) == []


def test_get_shaded_triangles_skips_first_when_p0_overlaps_p1() -> None:
    """When p0==p1 the first triangle (p0,p1,p3) is degenerate and skipped.
    The second triangle (p3,p1,p2) still emits → exactly 1 result.
    """
    patch = _patch()
    grid = [
        # p0 == p1: same coordinate (0,0)
        [_ccp((0.0, 0.0), [0.0]), _ccp((0.0, 0.0), [0.25])],
        [_ccp((0.0, 1.0), [0.5]),  _ccp((1.0, 1.0), [0.75])],
    ]
    triangles = patch.get_shaded_triangles(grid)
    assert len(triangles) == 1


def test_get_shaded_triangles_skips_both_when_second_quad_overlaps_too() -> None:
    """p2==p1 with the ``ll`` branch active triggers the ``continue``."""
    patch = _patch()
    # First triangle emitted (p0,p1,p3 distinct); then p2==p1 so we skip second.
    grid = [
        [_ccp((0.0, 0.0), [0.0]), _ccp((1.0, 1.0), [0.25])],
        [_ccp((0.0, 1.0), [0.5]),  _ccp((1.0, 1.0), [0.75])],
    ]
    triangles = patch.get_shaded_triangles(grid)
    assert len(triangles) == 1


# ---------------------------------------------------------------------------
# _CoordinateColorPair helper
# ---------------------------------------------------------------------------
def test_coordinate_color_pair_stores_independent_color_copy() -> None:
    original = [0.5, 0.5, 0.5]
    pair = _CoordinateColorPair((1.0, 2.0), original)
    original[0] = 9.0
    assert pair.color == [0.5, 0.5, 0.5]
    assert pair.coordinate == (1.0, 2.0)
