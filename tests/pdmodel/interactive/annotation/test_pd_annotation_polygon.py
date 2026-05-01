from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
    PDAnnotationPolygon,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)


def test_subtype_constant() -> None:
    assert PDAnnotationPolygon.SUB_TYPE == "Polygon"


def test_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationPolygon()
    assert ann.get_subtype() == "Polygon"


def test_extends_markup() -> None:
    ann = PDAnnotationPolygon()
    assert isinstance(ann, PDAnnotationMarkup)


def test_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Polygon")  # type: ignore[attr-defined]
    ann = PDAnnotationPolygon(d)
    assert ann.get_subtype() == "Polygon"
    assert ann.get_cos_object() is d


def test_vertices_default_none() -> None:
    assert PDAnnotationPolygon().get_vertices() is None


def test_vertices_round_trip() -> None:
    ann = PDAnnotationPolygon()
    ann.set_vertices([1.0, 2.0, 3.5, 4.5, 5.0, 6.0])
    assert ann.get_vertices() == [1.0, 2.0, 3.5, 4.5, 5.0, 6.0]


def test_vertices_clear() -> None:
    ann = PDAnnotationPolygon()
    ann.set_vertices([1.0, 2.0])
    ann.set_vertices(None)
    assert ann.get_vertices() is None


def test_interior_color_default_none() -> None:
    assert PDAnnotationPolygon().get_interior_color() is None


def test_interior_color_round_trip() -> None:
    ann = PDAnnotationPolygon()
    ann.set_interior_color((0.25, 0.5, 0.75))
    assert ann.get_interior_color() == (0.25, 0.5, 0.75)


def test_interior_color_clear() -> None:
    ann = PDAnnotationPolygon()
    ann.set_interior_color([0.5, 0.5, 0.5])
    ann.set_interior_color(None)
    assert ann.get_interior_color() is None


def test_border_style_round_trip() -> None:
    ann = PDAnnotationPolygon()
    bs = PDBorderStyleDictionary()
    bs.set_width(2.5)
    ann.set_border_style(bs)
    got = ann.get_border_style()
    assert got is not None
    assert got.get_width() == 2.5


def test_border_style_default_none() -> None:
    assert PDAnnotationPolygon().get_border_style() is None


def test_border_effect_round_trip() -> None:
    ann = PDAnnotationPolygon()
    be = COSDictionary()
    be.set_name(COSName.get_pdf_name("S"), "C")
    ann.set_border_effect(be)
    got = ann.get_border_effect()
    assert got is be


def test_factory_routes_to_polygon() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Polygon")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationPolygon)


def test_vertices_writes_cosfloat_array() -> None:
    ann = PDAnnotationPolygon()
    ann.set_vertices([1.0, 2.0, 3.0, 4.0])
    raw = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Vertices"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 4
    for item in raw:
        assert isinstance(item, COSFloat)


def test_polygon_get_path_default_none() -> None:
    assert PDAnnotationPolygon().get_path() is None


def test_polygon_get_path_returns_nested_arrays() -> None:
    ann = PDAnnotationPolygon()
    outer = COSArray()
    outer.add(COSArray([COSFloat(1.0), COSFloat(2.0)]))
    outer.add(COSArray([COSFloat(3.0), COSFloat(4.0), COSFloat(5.0), COSFloat(6.0)]))
    outer.add(
        COSArray(
            [
                COSFloat(7.0),
                COSFloat(8.0),
                COSFloat(9.0),
                COSFloat(10.0),
                COSFloat(11.0),
                COSFloat(12.0),
            ]
        )
    )
    ann.get_cos_object().set_item(COSName.get_pdf_name("Path"), outer)

    path = ann.get_path()
    assert path == [
        [1.0, 2.0],
        [3.0, 4.0, 5.0, 6.0],
        [7.0, 8.0, 9.0, 10.0, 11.0, 12.0],
    ]


def test_polygon_get_path_substitutes_empty_for_non_array() -> None:
    ann = PDAnnotationPolygon()
    outer = COSArray()
    outer.add(COSArray([COSFloat(1.0), COSFloat(2.0)]))
    outer.add(COSFloat(99.0))  # not a COSArray — should become []
    ann.get_cos_object().set_item(COSName.get_pdf_name("Path"), outer)

    assert ann.get_path() == [[1.0, 2.0], []]
