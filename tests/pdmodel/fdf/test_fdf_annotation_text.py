from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFAnnotationText


def test_default_constructor_stamps_subtype_text() -> None:
    a = FDFAnnotationText()
    assert a.get_subtype() == "Text"
    # /Type Annot inherited from base.
    assert a.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Type")) is COSName.get_pdf_name(
        "Annot"
    )


def test_existing_subtype_preserved() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Custom"))
    a = FDFAnnotationText(d)
    assert a.get_subtype() == "Custom"


def test_open_default_false_round_trip() -> None:
    a = FDFAnnotationText()
    assert a.get_open() is False
    a.set_open(True)
    assert a.get_open() is True


def test_icon_round_trip() -> None:
    a = FDFAnnotationText()
    assert a.get_icon() is None
    a.set_icon("Note")
    assert a.get_icon() == "Note"
    a.set_icon(None)
    assert a.get_icon() is None


def test_state_and_state_model_round_trip() -> None:
    a = FDFAnnotationText()
    a.set_state("Accepted")
    a.set_state_model("Review")
    assert a.get_state() == "Accepted"
    assert a.get_state_model() == "Review"


def test_rotation_default_zero() -> None:
    a = FDFAnnotationText()
    assert a.get_rotation() == 0
    a.set_rotation(90)
    assert a.get_rotation() == 90


def test_factory_dispatch_text() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text"))
    obj = FDFAnnotation.create(d)
    assert isinstance(obj, FDFAnnotationText)
