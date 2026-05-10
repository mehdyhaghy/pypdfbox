from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFAnnotationFreeText
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_default_constructor_stamps_subtype_free_text() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_subtype() == "FreeText"


def test_default_appearance_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_default_appearance() is None
    a.set_default_appearance("/Helv 12 Tf 0 g")
    assert a.get_default_appearance() == "/Helv 12 Tf 0 g"


def test_justification_string_round_trip() -> None:
    # Upstream getJustification returns the int as a string ("0"/"1"/"2").
    a = FDFAnnotationFreeText()
    assert a.get_justification() == "0"  # default left
    a.set_justification("centered")
    assert a.get_justification() == "1"
    a.set_justification("right")
    assert a.get_justification() == "2"
    a.set_justification("anything else")
    assert a.get_justification() == "0"


def test_justification_int_overload() -> None:
    a = FDFAnnotationFreeText()
    a.set_justification(FDFAnnotationFreeText.QUADDING_CENTERED)
    assert a.get_justification_int() == 1
    a.set_justification(FDFAnnotationFreeText.QUADDING_RIGHT)
    assert a.get_justification_int() == 2


def test_default_style_round_trip() -> None:
    a = FDFAnnotationFreeText()
    a.set_default_style("font: 12pt Helvetica")
    assert a.get_default_style() == "font: 12pt Helvetica"


def test_callout_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_callout() is None
    a.set_callout([1.0, 2.0, 3.0, 4.0])
    assert a.get_callout() == [1.0, 2.0, 3.0, 4.0]
    a.set_callout([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert a.get_callout() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    a.set_callout(None)
    assert a.get_callout() is None


def test_intent_round_trip() -> None:
    # Inherited from FDFAnnotation parent now (matches upstream).
    a = FDFAnnotationFreeText()
    assert a.get_intent() is None
    a.set_intent("FreeTextCallout")
    assert a.get_intent() == "FreeTextCallout"


def test_rotation_round_trip() -> None:
    # Upstream setRotation stores a COSInteger under /Rotate, and getRotation
    # is implemented via COSDictionary.getString which returns null for any
    # non-COSString entry. Mirror that quirk: get_rotation yields None even
    # after set_rotation(...). Use the raw cos object to read the int value.
    a = FDFAnnotationFreeText()
    assert a.get_rotation() is None
    a.set_rotation(180)
    assert a.get_rotation() is None
    assert a.get_cos_object().get_int(COSName.get_pdf_name("Rotate")) == 180


def test_line_ending_style_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_line_ending_style() is None
    a.set_line_ending_style("OpenArrow")
    assert a.get_line_ending_style() == "OpenArrow"
    a.set_line_ending_style(None)
    assert a.get_line_ending_style() is None


def test_rich_contents_round_trip() -> None:
    # Inherited from FDFAnnotation parent. Upstream returns "" for absent.
    a = FDFAnnotationFreeText()
    assert a.get_rich_contents() == ""
    a.set_rich_contents("<body>hi</body>")
    assert a.get_rich_contents() == "<body>hi</body>"


def test_fringe_round_trip() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_fringe() is None
    rect = PDRectangle()
    rect.set_lower_left_x(1.0)
    rect.set_lower_left_y(2.0)
    rect.set_upper_right_x(3.0)
    rect.set_upper_right_y(4.0)
    a.set_fringe(rect)
    out = a.get_fringe()
    assert out is not None
    assert (
        out.get_lower_left_x(),
        out.get_lower_left_y(),
        out.get_upper_right_x(),
        out.get_upper_right_y(),
    ) == (1.0, 2.0, 3.0, 4.0)
    a.set_fringe(None)
    assert a.get_fringe() is None


def test_init_callout_parses_string() -> None:
    a = FDFAnnotationFreeText()
    a.init_callout("1,2,3,4")
    assert a.get_callout() == [1.0, 2.0, 3.0, 4.0]
    # empty / None are no-ops
    a.set_callout(None)
    a.init_callout("")
    assert a.get_callout() is None
    a.init_callout(None)
    assert a.get_callout() is None


def test_init_fringe_parses_string() -> None:
    a = FDFAnnotationFreeText()
    a.init_fringe("1,2,3,4")
    out = a.get_fringe()
    assert out is not None
    assert out.get_lower_left_x() == 1.0
    # empty / None are no-ops
    a.set_fringe(None)
    a.init_fringe("")
    assert a.get_fringe() is None
    a.init_fringe(None)
    assert a.get_fringe() is None


def test_init_fringe_rejects_wrong_count() -> None:
    a = FDFAnnotationFreeText()
    with pytest.raises(OSError):
        a.init_fringe("1,2,3")


def test_factory_dispatch_free_text() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("FreeText"))
    obj = FDFAnnotation.create(d)
    assert isinstance(obj, FDFAnnotationFreeText)
