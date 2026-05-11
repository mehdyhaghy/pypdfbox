from __future__ import annotations

import pytest

from pypdfbox.pdmodel.fdf import FDFAnnotationPolygon


def test_default_constructor_sets_subtype() -> None:
    poly = FDFAnnotationPolygon()
    assert poly.get_cos_object().get_name_as_string("Subtype") == "Polygon"


def test_vertices_roundtrip() -> None:
    poly = FDFAnnotationPolygon()
    poly.set_vertices([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    out = poly.get_vertices()
    assert out == pytest.approx([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])


def test_vertices_none_clears() -> None:
    poly = FDFAnnotationPolygon()
    poly.set_vertices([1.0, 2.0])
    poly.set_vertices(None)
    assert poly.get_vertices() is None


def test_interior_color_roundtrip() -> None:
    poly = FDFAnnotationPolygon()
    poly.set_interior_color((0.1, 0.2, 0.3))
    assert poly.get_interior_color() == pytest.approx((0.1, 0.2, 0.3))


def test_interior_color_none_clears() -> None:
    poly = FDFAnnotationPolygon()
    poly.set_interior_color((1.0, 1.0, 1.0))
    poly.set_interior_color(None)
    assert poly.get_interior_color() is None
