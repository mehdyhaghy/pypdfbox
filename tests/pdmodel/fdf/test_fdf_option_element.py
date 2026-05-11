from __future__ import annotations

from pypdfbox.cos import COSArray, COSString
from pypdfbox.pdmodel.fdf import FDFOptionElement


def test_default_constructor_creates_two_empty_strings() -> None:
    opt = FDFOptionElement()
    arr = opt.get_cos_array()
    assert arr.size() == 2
    assert isinstance(arr.get_object(0), COSString)
    assert opt.get_option() == ""
    assert opt.get_default_appearance_string() == ""


def test_option_roundtrip() -> None:
    opt = FDFOptionElement()
    opt.set_option("Yes")
    assert opt.get_option() == "Yes"


def test_default_appearance_roundtrip() -> None:
    opt = FDFOptionElement()
    opt.set_default_appearance_string("/Helv 12 Tf 0 g")
    assert opt.get_default_appearance_string() == "/Helv 12 Tf 0 g"


def test_existing_array_preserved() -> None:
    arr = COSArray()
    arr.add(COSString("opt"))
    arr.add(COSString("da"))
    opt = FDFOptionElement(arr)
    assert opt.get_cos_array() is arr
    assert opt.get_cos_object() is arr
    assert opt.get_option() == "opt"
    assert opt.get_default_appearance_string() == "da"
