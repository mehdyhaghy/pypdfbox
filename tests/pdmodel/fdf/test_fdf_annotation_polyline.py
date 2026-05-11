from __future__ import annotations

import pytest

from pypdfbox.pdmodel.fdf import FDFAnnotationPolyline


def test_default_constructor_sets_subtype() -> None:
    poly = FDFAnnotationPolyline()
    assert poly.get_cos_object().get_name_as_string("Subtype") == "Polyline"


def test_vertices_roundtrip() -> None:
    poly = FDFAnnotationPolyline()
    poly.set_vertices([10.0, 20.0, 30.0, 40.0])
    assert poly.get_vertices() == pytest.approx([10.0, 20.0, 30.0, 40.0])


def test_start_point_style_default_when_absent() -> None:
    poly = FDFAnnotationPolyline()
    assert poly.get_start_point_ending_style() == "None"


def test_start_point_style_set() -> None:
    poly = FDFAnnotationPolyline()
    poly.set_start_point_ending_style("OpenArrow")
    assert poly.get_start_point_ending_style() == "OpenArrow"
    # End style should default to None for the second slot.
    assert poly.get_end_point_ending_style() == "None"


def test_end_point_style_set_with_existing_le_array() -> None:
    poly = FDFAnnotationPolyline()
    poly.set_start_point_ending_style("Square")
    poly.set_end_point_ending_style("Circle")
    assert poly.get_start_point_ending_style() == "Square"
    assert poly.get_end_point_ending_style() == "Circle"


def test_end_point_style_set_without_le_first() -> None:
    poly = FDFAnnotationPolyline()
    poly.set_end_point_ending_style("Circle")
    assert poly.get_end_point_ending_style() == "Circle"
    assert poly.get_start_point_ending_style() == "None"


def test_start_point_style_none_resets() -> None:
    poly = FDFAnnotationPolyline()
    poly.set_start_point_ending_style("Diamond")
    poly.set_start_point_ending_style(None)
    assert poly.get_start_point_ending_style() == "None"


def test_interior_color_roundtrip() -> None:
    poly = FDFAnnotationPolyline()
    poly.set_interior_color((0.25, 0.5, 0.75))
    assert poly.get_interior_color() == pytest.approx((0.25, 0.5, 0.75))


def test_interior_color_none_clears() -> None:
    poly = FDFAnnotationPolyline()
    poly.set_interior_color((0.0, 1.0, 0.0))
    poly.set_interior_color(None)
    assert poly.get_interior_color() is None
