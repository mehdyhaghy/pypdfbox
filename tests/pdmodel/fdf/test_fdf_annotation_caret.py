from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotationCaret
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_default_constructor_sets_subtype() -> None:
    caret = FDFAnnotationCaret()
    assert caret.get_cos_object().get_name_as_string("Subtype") == "Caret"


def test_get_set_fringe_roundtrip() -> None:
    caret = FDFAnnotationCaret()
    rect = PDRectangle(1.0, 2.0, 3.0, 4.0)
    caret.set_fringe(rect)
    out = caret.get_fringe()
    assert out is not None
    assert out.get_lower_left_x() == pytest.approx(1.0)
    assert out.get_upper_right_y() == pytest.approx(4.0)


def test_set_fringe_none_clears() -> None:
    caret = FDFAnnotationCaret()
    caret.set_fringe(PDRectangle(0.0, 0.0, 1.0, 1.0))
    caret.set_fringe(None)
    assert caret.get_fringe() is None


def test_get_fringe_invalid_array() -> None:
    annot = COSDictionary()
    annot.set_name("Subtype", "Caret")
    arr = COSArray()
    arr.add(COSFloat(1.0))
    annot.set_item(COSName.get_pdf_name("RD"), arr)
    caret = FDFAnnotationCaret(annot)
    assert caret.get_fringe() is None


def test_init_fringe_from_attribute() -> None:
    caret = FDFAnnotationCaret()
    caret.init_fringe("1,2,3,4")
    out = caret.get_fringe()
    assert out is not None
    assert out.get_upper_right_x() == pytest.approx(3.0)


def test_init_fringe_empty_no_op() -> None:
    caret = FDFAnnotationCaret()
    caret.init_fringe(None)
    caret.init_fringe("")
    assert caret.get_fringe() is None


def test_symbol_paragraph_maps_to_p() -> None:
    caret = FDFAnnotationCaret()
    caret.set_symbol("paragraph")
    assert caret.get_symbol() == "P"


def test_symbol_default_none() -> None:
    caret = FDFAnnotationCaret()
    caret.set_symbol("whatever")
    assert caret.get_symbol() == "None"


def test_existing_dict_skips_subtype_overwrite() -> None:
    annot = COSDictionary()
    annot.set_name("Subtype", "Caret")
    caret = FDFAnnotationCaret(annot)
    assert caret.get_cos_object() is annot
