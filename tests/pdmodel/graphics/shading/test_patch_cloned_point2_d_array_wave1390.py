"""Wave 1390 — close the final DEFERRED ``Patch`` surface.

Covers the newly-added ``Patch.cloned_point2_d_array`` static helper
(mirrors upstream ``Patch.clonedPoint2DArray`` at ``Patch.java:233``).
The clone must be a different container object with equal values and
defensively-copied elements, so callers can mutate one collection
without disturbing the other.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.pdmodel.graphics.shading.patch import Patch


def test_cloned_point2_d_array_returns_different_container_with_equal_values():
    points = ((1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0))
    cloned = Patch.cloned_point2_d_array(points)

    assert cloned is not points
    assert len(cloned) == len(points)
    for src, dst in zip(points, cloned, strict=True):
        assert math.isclose(src[0], dst[0])
        assert math.isclose(src[1], dst[1])


def test_cloned_point2_d_array_preserves_input():
    points = ((10.0, 20.0), (30.0, 40.0))
    _ = Patch.cloned_point2_d_array(points)
    # input untouched
    assert points == ((10.0, 20.0), (30.0, 40.0))


def test_cloned_point2_d_array_empty_input_returns_empty_tuple():
    out = Patch.cloned_point2_d_array(())
    assert out == ()
    assert isinstance(out, tuple)


def test_cloned_point2_d_array_accepts_list_input_returns_tuple():
    points = [(0.5, 1.5), (2.5, 3.5)]
    out = Patch.cloned_point2_d_array(points)
    assert isinstance(out, tuple)
    assert out == ((0.5, 1.5), (2.5, 3.5))
    # original list still mutable / unchanged
    assert points == [(0.5, 1.5), (2.5, 3.5)]


def test_cloned_point2_d_array_coerces_int_components_to_float():
    points = ((1, 2), (3, 4))
    out = Patch.cloned_point2_d_array(points)
    for p in out:
        assert isinstance(p[0], float)
        assert isinstance(p[1], float)


@pytest.mark.parametrize(
    "n",
    [1, 2, 4, 8, 16],
    ids=["one", "two", "four", "eight", "sixteen"],
)
def test_cloned_point2_d_array_round_trip_various_sizes(n):
    points = tuple((float(i), float(-i)) for i in range(n))
    out = Patch.cloned_point2_d_array(points)
    assert len(out) == n
    assert out == points
    assert out is not points


def test_cloned_point2_d_array_is_static_method():
    # Mirrors upstream `static Point2D[] clonedPoint2DArray(...)`.
    # Callable without an instance.
    assert callable(Patch.cloned_point2_d_array)
    # Direct unbound call works.
    out = Patch.cloned_point2_d_array(((1.0, 1.0),))
    assert out == ((1.0, 1.0),)
