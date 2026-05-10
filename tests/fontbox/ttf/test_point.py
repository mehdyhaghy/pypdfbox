"""Tests for :class:`pypdfbox.fontbox.ttf.point.Point`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.point import Point


def test_point_default_construction() -> None:
    p = Point()
    assert p.x == 0
    assert p.y == 0
    assert p.on_curve is True
    assert p.end_of_contour is False
    assert p.touched is False


def test_point_full_construction() -> None:
    p = Point(x=10, y=-5, on_curve=False, end_of_contour=True, touched=True)
    assert p.x == 10
    assert p.y == -5
    assert p.on_curve is False
    assert p.end_of_contour is True
    assert p.touched is True


def test_point_str_matches_upstream_shape() -> None:
    # Upstream toString (GlyphRenderer.java line 217):
    #   ``Point(x,y,onCurve,endOfContour)``
    p = Point(3, 7, on_curve=True, end_of_contour=True)
    assert str(p) == "Point(3,7,onCurve,endOfContour)"
    p2 = Point(0, 0, on_curve=False, end_of_contour=False)
    assert str(p2) == "Point(0,0,,)"


def test_point_equality_is_value_based() -> None:
    a = Point(1, 2, on_curve=True, end_of_contour=False)
    b = Point(1, 2, on_curve=True, end_of_contour=False)
    c = Point(1, 2, on_curve=False, end_of_contour=False)
    assert a == b
    assert a != c
