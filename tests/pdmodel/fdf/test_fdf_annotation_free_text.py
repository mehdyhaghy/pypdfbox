from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFAnnotationFreeText


def test_default_constructor_stamps_subtype_free_text() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_subtype() == "FreeText"


def test_default_appearance_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_default_appearance() is None
    a.set_default_appearance("/Helv 12 Tf 0 g")
    assert a.get_default_appearance() == "/Helv 12 Tf 0 g"


def test_justification_constants_and_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_justification() == 0  # default left
    a.set_justification(FDFAnnotationFreeText.QUADDING_CENTERED)
    assert a.get_justification() == 1
    a.set_justification(FDFAnnotationFreeText.QUADDING_RIGHT)
    assert a.get_justification() == 2


def test_default_style_round_trip() -> None:
    a = FDFAnnotationFreeText()
    a.set_default_style("font: 12pt Helvetica")
    assert a.get_default_style() == "font: 12pt Helvetica"


def test_callout_line_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_callout_line() is None
    a.set_callout_line([1.0, 2.0, 3.0, 4.0])
    assert a.get_callout_line() == [1.0, 2.0, 3.0, 4.0]
    a.set_callout_line([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert a.get_callout_line() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    a.set_callout_line(None)
    assert a.get_callout_line() is None


def test_intent_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_intent() is None
    a.set_intent("FreeTextCallout")
    assert a.get_intent() == "FreeTextCallout"
    a.set_intent(None)
    assert a.get_intent() is None


def test_rotation_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_rotation() == 0
    a.set_rotation(180)
    assert a.get_rotation() == 180


def test_line_ending_style_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_line_ending_style() is None
    a.set_line_ending_style("OpenArrow")
    assert a.get_line_ending_style() == "OpenArrow"
    a.set_line_ending_style(None)
    assert a.get_line_ending_style() is None


def test_rich_contents_round_trip() -> None:
    a = FDFAnnotationFreeText()
    a.set_rich_contents("<body>hi</body>")
    assert a.get_rich_contents() == "<body>hi</body>"


def test_factory_dispatch_free_text() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("FreeText"))
    obj = FDFAnnotation.create(d)
    assert isinstance(obj, FDFAnnotationFreeText)
