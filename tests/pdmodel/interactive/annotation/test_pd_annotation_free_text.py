from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
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
