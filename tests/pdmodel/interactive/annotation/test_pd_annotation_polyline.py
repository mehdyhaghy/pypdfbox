from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
    PDAnnotationPolyline,
)


def test_subtype_constant() -> None:
    assert PDAnnotationPolyline.SUB_TYPE == "PolyLine"


def test_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationPolyline()
    assert ann.get_subtype() == "PolyLine"


def test_extends_markup() -> None:
    ann = PDAnnotationPolyline()
    assert isinstance(ann, PDAnnotationMarkup)


def test_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "PolyLine")  # type: ignore[attr-defined]
    ann = PDAnnotationPolyline(d)
    assert ann.get_subtype() == "PolyLine"
    assert ann.get_cos_object() is d


def test_vertices_default_none() -> None:
    assert PDAnnotationPolyline().get_vertices() is None


def test_vertices_round_trip() -> None:
    ann = PDAnnotationPolyline()
    ann.set_vertices([10.0, 20.0, 30.0, 40.0])
    assert ann.get_vertices() == [10.0, 20.0, 30.0, 40.0]


def test_line_ending_styles_default_none() -> None:
    assert PDAnnotationPolyline().get_line_ending_styles() is None


def test_line_ending_styles_round_trip() -> None:
    ann = PDAnnotationPolyline()
    ann.set_line_ending_styles("OpenArrow", "ClosedArrow")
    assert ann.get_line_ending_styles() == ("OpenArrow", "ClosedArrow")


def test_line_ending_styles_writes_two_names() -> None:
    ann = PDAnnotationPolyline()
    ann.set_line_ending_styles("Square", "Circle")
    raw = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("LE"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 2


def test_factory_routes_to_polyline() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "PolyLine")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationPolyline)


def test_subtype_capitalization_sensitivity() -> None:
    # Spec uses 'PolyLine' (capital L). 'Polyline' should NOT route here.
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Polyline")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert not isinstance(ann, PDAnnotationPolyline)


def test_interior_color_round_trip() -> None:
    ann = PDAnnotationPolyline()
    ann.set_interior_color((1.0, 0.0, 0.0))
    assert ann.get_interior_color() == (1.0, 0.0, 0.0)


def test_markup_creation_date_inherited() -> None:
    ann = PDAnnotationPolyline()
    ann.set_creation_date("D:20260427100000Z")
    assert ann.get_creation_date() == "D:20260427100000Z"
