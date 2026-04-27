from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotation


def test_default_constructor_stamps_type_annot() -> None:
    a = FDFAnnotation()
    assert a.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Type")) is COSName.get_pdf_name(
        "Annot"
    )


def test_wraps_existing_dict_without_overwriting_type() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Custom"))
    a = FDFAnnotation(d)
    # Existing /Type respected.
    assert a.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Type")) is COSName.get_pdf_name(
        "Custom"
    )


def test_page_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_page() == -1  # default sentinel from get_int
    a.set_page(3)
    assert a.get_page() == 3


def test_name_contents_title_round_trip() -> None:
    a = FDFAnnotation()
    a.set_name("annot-1")
    a.set_contents("hello world")
    a.set_title("alice")
    assert a.get_name() == "annot-1"
    assert a.get_contents() == "hello world"
    assert a.get_title() == "alice"


def test_subtype_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_subtype() is None
    a.set_subtype("Text")
    assert a.get_subtype() == "Text"
    a.set_subtype(None)
    assert a.get_subtype() is None


def test_rectangle_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_rectangle() is None
    a.set_rectangle((10.0, 20.0, 30.5, 40.5))
    assert a.get_rectangle() == (10.0, 20.0, 30.5, 40.5)
    a.set_rectangle(None)
    assert a.get_rectangle() is None


def test_color_round_trip() -> None:
    a = FDFAnnotation()
    assert a.get_color() is None
    a.set_color((1.0, 0.5, 0.0))
    assert a.get_color() == (1.0, 0.5, 0.0)


def test_flags_default_zero() -> None:
    a = FDFAnnotation()
    assert a.get_flags() == 0
    a.set_flags(7)
    assert a.get_flags() == 7


def test_name_attribute_round_trip() -> None:
    a = FDFAnnotation()
    a.set_name_attribute("Note")
    assert a.get_name_attribute() == "Note"


def test_modified_date_round_trip() -> None:
    a = FDFAnnotation()
    a.set_modified_date("D:20260427120000Z")
    assert a.get_modified_date() == "D:20260427120000Z"
