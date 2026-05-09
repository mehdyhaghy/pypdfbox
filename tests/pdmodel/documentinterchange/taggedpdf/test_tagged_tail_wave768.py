from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.documentinterchange import taggedpdf
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDFourColours,
    PDListAttributeObject,
    PDPrintFieldAttributeObject,
)


def test_print_field_clear_checked_alias_removes_checked_wave768() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_checked_state(PDPrintFieldAttributeObject.CHECKED_STATE_ON)

    obj.clear_checked()

    assert obj.has_checked_state() is False
    assert obj.get_checked_state() == PDPrintFieldAttributeObject.CHECKED_STATE_OFF


def test_print_field_clear_desc_alias_removes_desc_wave768() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_alternate_name("visible label")

    obj.clear_desc()

    assert obj.has_alternate_name() is False
    assert obj.get_alternate_name() is None


def test_print_field_clear_description_alias_removes_desc_wave768() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_description("visible label")

    obj.clear_description()

    assert obj.has_alternate_name() is False
    assert obj.get_description() is None


def test_print_field_repr_includes_owner_role_and_default_checked_wave768() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_role(PDPrintFieldAttributeObject.ROLE_PUSH_BUTTON)

    assert repr(obj) == (
        "PDPrintFieldAttributeObject(O=PrintField, Role=pb, checked=off)"
    )


def test_four_colours_returns_none_for_non_numeric_component_wave768() -> None:
    bad_colour = COSArray()
    bad_colour.add(COSName.get_pdf_name("Red"))
    backing = COSArray([bad_colour, COSArray(), COSArray(), COSArray()])
    four = PDFourColours(backing)

    assert four.get_before_colour() is None


def test_list_attribute_repr_includes_owner_and_list_numbering_wave768() -> None:
    obj = PDListAttributeObject()
    obj.set_list_numbering(PDListAttributeObject.LIST_NUMBERING_DECIMAL)

    assert repr(obj) == "PDListAttributeObject(O=List, ListNumbering=Decimal)"


def test_taggedpdf_getattr_unknown_name_raises_attribute_error_wave768() -> None:
    with pytest.raises(AttributeError, match="MissingAttribute"):
        taggedpdf.__getattr__("MissingAttribute")
