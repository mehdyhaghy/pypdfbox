"""Wave 267 round-out: PDAnnotationPolygon predicates / vertex helpers.

Covers:
- ``has_vertices`` / ``has_path`` / ``has_border_effect`` /
  ``has_interior_color`` / ``has_measure`` predicates
- ``vertex_count`` (count of (x,y) pairs; trailing-odd-coord handling)
- ``iter_vertex_points`` (alternating-coord -> point pairs)
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
    PDAnnotationPolygon,
)

_VERTICES_NAME = COSName.get_pdf_name("Vertices")
_PATH_NAME = COSName.get_pdf_name("Path")


# ---------- has_vertices ----------


def test_has_vertices_default_false() -> None:
    assert PDAnnotationPolygon().has_vertices() is False


def test_has_vertices_true_after_set() -> None:
    ann = PDAnnotationPolygon()
    ann.set_vertices([1.0, 2.0, 3.0, 4.0])
    assert ann.has_vertices() is True


def test_has_vertices_true_for_empty_array() -> None:
    """Empty array still present — predicate distinguishes from absent."""
    ann = PDAnnotationPolygon()
    ann.get_cos_object().set_item(_VERTICES_NAME, COSArray())
    assert ann.has_vertices() is True


def test_has_vertices_false_after_clear() -> None:
    ann = PDAnnotationPolygon()
    ann.set_vertices([1.0, 2.0])
    ann.set_vertices(None)
    assert ann.has_vertices() is False


# ---------- vertex_count ----------


def test_vertex_count_default_zero() -> None:
    assert PDAnnotationPolygon().vertex_count() == 0


def test_vertex_count_pairs() -> None:
    ann = PDAnnotationPolygon()
    ann.set_vertices([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert ann.vertex_count() == 3


def test_vertex_count_drops_trailing_odd_coord() -> None:
    """Trailing odd coord (malformed input) is dropped per spec which
    requires an even number of coordinates."""
    ann = PDAnnotationPolygon()
    ann.set_vertices([1.0, 2.0, 3.0])  # bogus odd length
    assert ann.vertex_count() == 1


def test_vertex_count_empty_array_zero() -> None:
    ann = PDAnnotationPolygon()
    ann.get_cos_object().set_item(_VERTICES_NAME, COSArray())
    assert ann.vertex_count() == 0


# ---------- iter_vertex_points ----------


def test_iter_vertex_points_default_empty() -> None:
    assert PDAnnotationPolygon().iter_vertex_points() == []


def test_iter_vertex_points_pairs_floats() -> None:
    ann = PDAnnotationPolygon()
    ann.set_vertices([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    assert ann.iter_vertex_points() == [
        (10.0, 20.0),
        (30.0, 40.0),
        (50.0, 60.0),
    ]


def test_iter_vertex_points_drops_trailing_odd_coord() -> None:
    ann = PDAnnotationPolygon()
    ann.set_vertices([1.0, 2.0, 3.0])
    assert ann.iter_vertex_points() == [(1.0, 2.0)]


# ---------- has_path (PDF 2.0) ----------


def test_has_path_default_false() -> None:
    assert PDAnnotationPolygon().has_path() is False


def test_has_path_true_when_present() -> None:
    ann = PDAnnotationPolygon()
    outer = COSArray()
    outer.add(COSArray([COSFloat(1.0), COSFloat(2.0)]))
    ann.get_cos_object().set_item(_PATH_NAME, outer)
    assert ann.has_path() is True


# ---------- has_border_effect ----------


def test_has_border_effect_default_false() -> None:
    assert PDAnnotationPolygon().has_border_effect() is False


def test_has_border_effect_true_after_set() -> None:
    ann = PDAnnotationPolygon()
    be = COSDictionary()
    be.set_name(COSName.get_pdf_name("S"), "C")
    ann.set_border_effect(be)
    assert ann.has_border_effect() is True


def test_has_border_effect_false_after_clear() -> None:
    ann = PDAnnotationPolygon()
    be = COSDictionary()
    ann.set_border_effect(be)
    ann.set_border_effect(None)
    assert ann.has_border_effect() is False


# ---------- has_interior_color ----------


def test_has_interior_color_default_false() -> None:
    assert PDAnnotationPolygon().has_interior_color() is False


def test_has_interior_color_true_after_set() -> None:
    ann = PDAnnotationPolygon()
    ann.set_interior_color((0.1, 0.2, 0.3))
    assert ann.has_interior_color() is True


def test_has_interior_color_false_after_clear() -> None:
    ann = PDAnnotationPolygon()
    ann.set_interior_color((0.5, 0.5, 0.5))
    ann.set_interior_color(None)
    assert ann.has_interior_color() is False


# ---------- has_measure ----------


def test_has_measure_default_false() -> None:
    assert PDAnnotationPolygon().has_measure() is False


def test_has_measure_true_after_set() -> None:
    ann = PDAnnotationPolygon()
    ann.set_measure(COSDictionary())
    assert ann.has_measure() is True
