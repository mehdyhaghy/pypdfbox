from __future__ import annotations

import datetime as dt

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotation, PDAnnotationText
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_unknown import (
    PDAnnotationUnknown,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave598_constructor_and_factory_reject_non_dictionary_inputs() -> None:
    with pytest.raises(TypeError, match="PDAnnotation requires a COSDictionary"):
        PDAnnotation(COSArray())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="PDAnnotation.create expects a COSDictionary"):
        PDAnnotation.create(COSString("bad"))


def test_wave598_subtype_round_trip_clear_and_unknown_dispatch() -> None:
    annotation = PDAnnotation()

    annotation.set_subtype("CustomSubtype")
    assert annotation.get_subtype() == "CustomSubtype"
    assert isinstance(PDAnnotation.create(annotation.get_cos_object()), PDAnnotationUnknown)

    annotation.set_subtype(None)
    assert annotation.get_subtype() is None


def test_wave598_rectangle_and_contents_presence_predicates() -> None:
    annotation = PDAnnotationText()

    annotation.set_contents("")
    assert annotation.has_contents() is False

    annotation.set_contents("visible")
    assert annotation.has_contents() is True

    annotation.set_rectangle(PDRectangle(1.0, 2.0, 3.0, 4.0))
    rect = annotation.get_rect()
    assert rect is not None
    assert rect.get_lower_left_x() == 1.0
    assert annotation.has_rectangle() is True

    annotation.get_cos_object().set_item(
        _name("Rect"),
        COSArray(
            [
                COSInteger.get(1),
                COSString("bad"),
                COSInteger.get(3),
                COSInteger.get(4),
            ]
        ),
    )
    with pytest.raises(TypeError, match="PDRectangle entry 1 is not numeric"):
        annotation.get_rectangle()

    annotation.set_rectangle(None)
    assert annotation.get_rectangle() is None


def test_wave598_modified_date_keeps_raw_strings_and_formats_negative_offset() -> None:
    annotation = PDAnnotationText()

    annotation.set_modified_date("D:20260508010203-05'00'")
    assert annotation.get_modified_date() == "D:20260508010203-05'00'"

    offset = dt.timezone(dt.timedelta(hours=-5, minutes=-30))
    annotation.set_modified_date(dt.datetime(2026, 5, 8, 1, 2, 3, tzinfo=offset))

    assert annotation.get_modified_date() == "D:20260508010203-05'30'"


def test_wave598_set_color_rejects_duck_typed_non_array_result() -> None:
    annotation = PDAnnotationText()

    class BadColor:
        def to_cos_array(self) -> COSString:
            return COSString("not-array")

    with pytest.raises(TypeError, match="set_color expects"):
        annotation.set_color(BadColor())


def test_wave598_appearance_dictionary_aliases_wrap_and_clear() -> None:
    annotation = PDAnnotationText()
    appearance = COSDictionary()

    annotation.set_appearance(appearance)

    assert annotation.has_appearance() is True
    wrapped = annotation.get_appearance()
    assert wrapped is not None
    assert wrapped.get_cos_object() is appearance

    annotation.set_appearance_dictionary(None)

    assert annotation.has_appearance() is False
    assert annotation.get_appearance_dictionary() is None
