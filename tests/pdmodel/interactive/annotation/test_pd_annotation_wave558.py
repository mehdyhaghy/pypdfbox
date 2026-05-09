from __future__ import annotations

import datetime as dt

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationCaret,
    PDAnnotationFileAttachment,
    PDAnnotationFreeText,
    PDAnnotationHighlight,
    PDAnnotationInk,
    PDAnnotationLine,
    PDAnnotationPolygon,
    PDAnnotationPolyline,
    PDAnnotationPopup,
    PDAnnotationRubberStamp,
    PDAnnotationScreen,
    PDAnnotationSound,
    PDAnnotationSquiggly,
    PDAnnotationStrikeout,
    PDAnnotationText,
    PDAnnotationUnderline,
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_movie import (
    PDAnnotationMovie,
)


def _annotation_dict(subtype: str) -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_name(COSName.SUBTYPE, subtype)  # type: ignore[attr-defined]
    return dictionary


@pytest.mark.parametrize(
    ("subtype", "expected_cls"),
    [
        ("Widget", PDAnnotationWidget),
        ("Line", PDAnnotationLine),
        ("FreeText", PDAnnotationFreeText),
        ("FileAttachment", PDAnnotationFileAttachment),
        ("Stamp", PDAnnotationRubberStamp),
        ("Popup", PDAnnotationPopup),
        ("Highlight", PDAnnotationHighlight),
        ("Underline", PDAnnotationUnderline),
        ("StrikeOut", PDAnnotationStrikeout),
        ("Squiggly", PDAnnotationSquiggly),
        ("Caret", PDAnnotationCaret),
        ("Ink", PDAnnotationInk),
        ("Polygon", PDAnnotationPolygon),
        ("PolyLine", PDAnnotationPolyline),
        ("Movie", PDAnnotationMovie),
        ("Sound", PDAnnotationSound),
        ("Screen", PDAnnotationScreen),
    ],
)
def test_wave558_create_dispatches_remaining_common_subtypes(
    subtype: str, expected_cls: type[PDAnnotation]
) -> None:
    assert isinstance(PDAnnotation.create(_annotation_dict(subtype)), expected_cls)


def test_wave558_base_constructor_rejects_non_dictionary() -> None:
    with pytest.raises(TypeError, match="PDAnnotation requires a COSDictionary"):
        PDAnnotation(COSName.get_pdf_name("Annot"))  # type: ignore[arg-type]


def test_wave558_set_subtype_writes_and_removes_name() -> None:
    annotation = PDAnnotation()

    annotation.set_subtype("Text")
    assert annotation.get_subtype() == "Text"

    annotation.set_subtype(None)
    assert annotation.get_subtype() is None


def test_wave558_get_rect_alias_returns_rectangle() -> None:
    annotation = PDAnnotationText()
    rect = COSArray()
    for value in (1.0, 2.0, 3.0, 4.0):
        rect.add(COSFloat(value))
    annotation.get_cos_object().set_item(COSName.get_pdf_name("Rect"), rect)

    assert annotation.get_rect() is not None


def test_wave558_modified_date_formats_positive_and_negative_offsets() -> None:
    annotation = PDAnnotationText()

    annotation.set_modified_date(
        dt.datetime(
            2024,
            1,
            2,
            3,
            4,
            5,
            tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)),
        )
    )
    assert annotation.get_modified_date() == "D:20240102030405+05'30'"

    annotation.set_modified_date(
        dt.datetime(
            2024,
            1,
            2,
            3,
            4,
            5,
            tzinfo=dt.timezone(-dt.timedelta(hours=7)),
        )
    )
    assert annotation.get_modified_date() == "D:20240102030405-07'00'"


def test_wave558_set_p_accepts_page_like_object_and_rejects_bad_objects() -> None:
    annotation = PDAnnotationText()
    page_dict = COSDictionary()

    class _PageLike:
        def get_cos_object(self) -> COSDictionary:
            return page_dict

    annotation.set_p(_PageLike())
    assert annotation.get_p() is page_dict

    class _BadPageLike:
        def get_cos_object(self) -> COSString:
            return COSString("not-a-dictionary")

    with pytest.raises(TypeError, match="COSDictionary"):
        annotation.set_p(_BadPageLike())

    with pytest.raises(TypeError, match="set_p expects"):
        annotation.set_p("not-a-page")


def test_wave558_struct_parent_round_trip() -> None:
    annotation = PDAnnotationText()

    assert annotation.get_struct_parent() == -1
    annotation.set_struct_parent(12)
    assert annotation.get_struct_parent() == 12


def test_wave558_optional_content_round_trips_supported_inputs() -> None:
    annotation = PDAnnotationText()
    raw = COSDictionary()

    annotation.set_optional_content(raw)
    assert isinstance(annotation.get_optional_content(), PDPropertyList)
    assert annotation.get_optional_content().get_cos_object() is raw

    group = PDOptionalContentGroup("Layer")
    annotation.set_optional_content(group)
    optional_content = annotation.get_optional_content()
    assert isinstance(optional_content, PDOptionalContentGroup)
    assert optional_content.get_cos_object() is group.get_cos_object()

    annotation.set_optional_content(None)
    assert annotation.get_optional_content() is None


def test_wave558_optional_content_rejects_bad_objects() -> None:
    annotation = PDAnnotationText()

    class _BadPropertyList:
        def get_cos_object(self) -> COSString:
            return COSString("not-a-dictionary")

    with pytest.raises(TypeError, match="COSDictionary-backed"):
        annotation.set_optional_content(_BadPropertyList())

    with pytest.raises(TypeError, match="set_optional_content expects"):
        annotation.set_optional_content("not-optional-content")

    annotation.get_cos_object().set_item(
        COSName.get_pdf_name("OC"), COSName.get_pdf_name("NotADictionary")
    )
    assert annotation.get_optional_content() is None


def test_wave558_base_construct_appearances_is_noop() -> None:
    assert PDAnnotationText().construct_appearances() is None


def test_wave558_hash_and_repr_use_backing_dictionary_and_subtype() -> None:
    annotation = PDAnnotationText()

    assert hash(annotation) == id(annotation.get_cos_object())
    assert repr(annotation) == "PDAnnotationText(subtype='Text')"
    assert annotation.__eq__(object()) is NotImplemented
