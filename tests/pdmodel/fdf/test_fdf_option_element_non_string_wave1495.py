"""Wave 1495 — behaviour-anchored coverage for ``FDFOptionElement``'s
non-``COSString`` fallbacks: when the wrapped ``/Opt`` array holds a non-string
(or missing) entry at index 0/1, the getters return ``""`` rather than raising.

Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFOptionElement``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSString
from pypdfbox.pdmodel.fdf.fdf_option_element import FDFOptionElement


def test_get_option_returns_empty_when_index0_not_a_cos_string() -> None:
    array = COSArray()
    array.add(COSInteger(5))  # index 0 is an integer, not a string
    array.add(COSString("da"))
    element = FDFOptionElement(array)
    assert element.get_option() == ""
    # index 1 is a real string and still resolves normally.
    assert element.get_default_appearance_string() == "da"


def test_get_default_appearance_returns_empty_when_index1_not_a_cos_string() -> None:
    array = COSArray()
    array.add(COSString("opt"))
    array.add(COSInteger(9))  # index 1 is an integer, not a string
    element = FDFOptionElement(array)
    assert element.get_default_appearance_string() == ""
    assert element.get_option() == "opt"


def test_wrapped_array_is_returned_as_is() -> None:
    array = COSArray()
    array.add(COSString("opt"))
    array.add(COSString("da"))
    element = FDFOptionElement(array)
    assert element.get_cos_object() is array
    assert element.get_cos_array() is array
