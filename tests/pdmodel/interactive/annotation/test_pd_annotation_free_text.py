from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_free_text_subtype_constant() -> None:
    assert PDAnnotationFreeText.SUB_TYPE == "FreeText"


def test_free_text_inherits_markup() -> None:
    # Upstream class hierarchy: PDAnnotation -> PDAnnotationMarkup ->
    # PDAnnotationFreeText.
    assert issubclass(PDAnnotationFreeText, PDAnnotationMarkup)


def test_free_text_default_constructor_sets_type_and_subtype() -> None:
    ann = PDAnnotationFreeText()
    cos = ann.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]
    assert ann.get_subtype() == "FreeText"


def test_free_text_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "FreeText")  # type: ignore[attr-defined]
    ann = PDAnnotationFreeText(d)
    assert ann.get_subtype() == "FreeText"
    assert ann.get_cos_object() is d


def test_free_text_inherits_markup_creation_date() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_creation_date() is None
    ann.set_creation_date("D:20260101120000Z00'00'")
    assert ann.get_creation_date() == "D:20260101120000Z00'00'"


def test_free_text_inherits_markup_constant_opacity_default() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_constant_opacity() == 1.0


def test_free_text_inherits_markup_subject() -> None:
    ann = PDAnnotationFreeText()
    ann.set_subject("Annotation")
    assert ann.get_subject() == "Annotation"


def test_free_text_intent_round_trip_via_local_accessor() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_intent() is None
    ann.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    assert ann.get_intent() == "FreeTextCallout"
    ann.set_intent(None)
    assert ann.get_intent() is None


def test_free_text_default_appearance_clear() -> None:
    ann = PDAnnotationFreeText()
    ann.set_default_appearance("/Helv 12 Tf 0 g")
    ann.set_default_appearance(None)
    assert ann.get_default_appearance() is None


def test_free_text_callout_line_clear_when_unset() -> None:
    ann = PDAnnotationFreeText()
    ann.set_callout_line(None)
    assert ann.get_callout_line() is None


def test_free_text_line_ending_default_returns_line_le_none() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_line_ending() == PDAnnotationLine.LE_NONE


def test_free_text_factory_dispatch() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "FreeText")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationFreeText)
    assert ann.get_subtype() == "FreeText"


# ---------- /RD as PDRectangle (singular upstream accessors) ----------


def test_free_text_rect_difference_default_none() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_rect_difference() is None


def test_free_text_rect_difference_round_trip() -> None:
    ann = PDAnnotationFreeText()
    rect = PDRectangle(2.0, 3.0, 5.0, 7.0)
    ann.set_rect_difference(rect)

    rt = ann.get_rect_difference()
    assert rt is not None
    # PDRectangle normalizes to (min, min, max, max) — our values already
    # are in (lower-left, upper-right) order so round-trip is exact.
    assert rt.get_lower_left_x() == 2.0
    assert rt.get_lower_left_y() == 3.0
    assert rt.get_upper_right_x() == 5.0
    assert rt.get_upper_right_y() == 7.0


def test_free_text_rect_difference_clear() -> None:
    ann = PDAnnotationFreeText()
    ann.set_rect_difference(PDRectangle(1.0, 2.0, 3.0, 4.0))
    ann.set_rect_difference(None)
    assert ann.get_rect_difference() is None


def test_free_text_rect_difference_via_plural_round_trip() -> None:
    """Both plural and singular accessors read/write the same ``/RD`` entry."""
    ann = PDAnnotationFreeText()
    ann.set_rectangle_differences([1.0, 2.0, 3.0, 4.0])

    rt = ann.get_rect_difference()
    assert rt is not None
    assert rt.get_lower_left_x() == 1.0
    assert rt.get_upper_right_y() == 4.0


def test_free_text_rect_difference_short_array_returns_none() -> None:
    ann = PDAnnotationFreeText()
    cos = ann.get_cos_object()
    cos.set_item(  # type: ignore[attr-defined]
        COSName.get_pdf_name("RD"),
        COSArray([COSFloat(1.0), COSFloat(2.0)]),
    )
    assert ann.get_rect_difference() is None
