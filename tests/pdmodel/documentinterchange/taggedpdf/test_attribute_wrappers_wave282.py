from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDExportFormatAttributeObject,
    PDLayoutAttributeObject,
    PDListAttributeObject,
    PDPrintFieldAttributeObject,
    PDStandardAttributeObject,
    PDTableAttributeObject,
)


class _ConcreteStandard(PDStandardAttributeObject):
    """Concrete shell for the standard helper surface."""


def test_clear_attribute_alias_removes_raw_entry() -> None:
    obj = _ConcreteStandard()
    obj.set_string("Desc", "hello")
    assert obj.has_attribute("Desc")

    obj.clear_attribute("Desc")

    assert not obj.has_attribute("Desc")
    assert obj.get_string("Desc") is None


def test_name_array_getter_rejects_malformed_cos_array() -> None:
    obj = PDLayoutAttributeObject()
    raw = COSArray()
    raw.add(COSName.get_pdf_name("Solid"))
    raw.add(COSString("not-a-name"))
    obj.get_cos_object().set_item("BorderStyle", raw)

    assert obj.get_border_style() is None


def test_number_array_getter_rejects_malformed_cos_array() -> None:
    obj = PDLayoutAttributeObject()
    raw = COSArray()
    raw.add(COSFloat(1.0))
    raw.add(COSName.get_pdf_name("not-a-number"))
    obj.get_cos_object().set_item("Padding", raw)

    assert obj.get_padding() is None


def test_four_colour_getter_rejects_malformed_four_slot_array() -> None:
    obj = PDLayoutAttributeObject()
    raw = COSArray()
    for value in ("a", "b", "c", "d"):
        raw.add(COSName.get_pdf_name(value))
    obj.get_cos_object().set_item("BorderColor", raw)

    assert obj.get_border_colors() is None


def test_bool_is_rejected_for_number_or_array_layout_setters() -> None:
    obj = PDLayoutAttributeObject()

    with pytest.raises(TypeError):
        obj.set_padding(True)


def test_list_attribute_has_and_clear_list_numbering() -> None:
    obj = PDListAttributeObject()
    assert not obj.has_list_numbering()

    obj.set_list_numbering(PDListAttributeObject.LIST_NUMBERING_DECIMAL)
    assert obj.has_list_numbering()

    obj.clear_list_numbering()
    assert not obj.has_list_numbering()
    assert obj.get_list_numbering() == PDListAttributeObject.LIST_NUMBERING_NONE


def test_print_field_has_and_clear_helpers() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_role(PDPrintFieldAttributeObject.ROLE_RADIO_BUTTON)
    obj.set_checked_state(PDPrintFieldAttributeObject.CHECKED_STATE_ON)
    obj.set_alternate_name("Choice")

    assert obj.has_role()
    assert obj.has_checked_state()
    assert obj.has_alternate_name()

    obj.clear_role()
    obj.clear_checked_state()
    obj.clear_alternate_name()

    assert not obj.has_role()
    assert not obj.has_checked_state()
    assert not obj.has_alternate_name()
    assert obj.get_checked_state() == PDPrintFieldAttributeObject.CHECKED_STATE_OFF


def test_table_attribute_has_and_clear_helpers() -> None:
    obj = PDTableAttributeObject()
    obj.set_row_span(2)
    obj.set_headers(["h1"])

    assert obj.has_row_span()
    assert obj.has_headers()

    obj.clear_row_span()
    obj.clear_headers()

    assert not obj.has_row_span()
    assert not obj.has_headers()
    assert obj.get_row_span() == 1
    assert obj.get_headers() == []


def test_export_format_has_and_clear_helpers() -> None:
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    obj.set_list_numbering(PDExportFormatAttributeObject.LIST_NUMBERING_DECIMAL)
    obj.set_summary("summary")

    assert obj.has_list_numbering()
    assert obj.has_summary()

    obj.clear_list_numbering()
    obj.clear_summary()

    assert not obj.has_list_numbering()
    assert not obj.has_summary()
    assert obj.get_list_numbering() == PDExportFormatAttributeObject.LIST_NUMBERING_NONE
    assert obj.get_summary() is None
