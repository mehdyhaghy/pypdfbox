from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
    PDAnnotationPolygon,
)


def test_wave315_polygon_set_path_round_trips_pdf20_operands() -> None:
    ann = PDAnnotationPolygon()

    ann.set_path(
        [
            [1.0, 2.0],
            [3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        ]
    )

    assert ann.get_path() == [
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    ]


def test_wave315_polygon_set_path_writes_nested_cosfloat_arrays() -> None:
    ann = PDAnnotationPolygon()

    ann.set_path([(1, 2), (3.5, 4.5)])

    raw = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Path"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    for inner in raw:
        assert isinstance(inner, COSArray)
        for operand in inner:
            assert isinstance(operand, COSFloat)


def test_wave315_polygon_set_path_none_removes_entry() -> None:
    ann = PDAnnotationPolygon()
    ann.set_path([[1.0, 2.0]])

    ann.set_path(None)

    assert ann.get_path() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("Path"))
