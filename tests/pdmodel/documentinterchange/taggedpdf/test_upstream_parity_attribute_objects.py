"""Upstream-parity tests for the standard attribute object cluster.

These tests pin the upstream PDFBox 3.0.x public surface — owner-name
constants, dictionary-key constants, the ``getCheckedState`` /
``getAlternateName`` accessors on PrintField, and the
``PDExportFormatAttributeObject extends PDLayoutAttributeObject``
inheritance — independently of the pypdfbox-style aliases exercised by
the sibling test files. There is no upstream JUnit test for these
classes, so they live alongside the hand-written tests rather than under
``upstream/``.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDExportFormatAttributeObject,
    PDLayoutAttributeObject,
    PDListAttributeObject,
    PDPrintFieldAttributeObject,
    PDStandardAttributeObject,
    PDTableAttributeObject,
)


# ---------- upstream-parity owner constants ----------


def test_list_owner_constant_is_owner_list() -> None:
    assert PDListAttributeObject.OWNER_LIST == "List"
    assert PDListAttributeObject().get_owner() == PDListAttributeObject.OWNER_LIST


def test_print_field_owner_constant_is_owner_print_field() -> None:
    assert PDPrintFieldAttributeObject.OWNER_PRINT_FIELD == "PrintField"
    obj = PDPrintFieldAttributeObject()
    assert obj.get_owner() == PDPrintFieldAttributeObject.OWNER_PRINT_FIELD


def test_table_owner_constant_is_owner_table() -> None:
    assert PDTableAttributeObject.OWNER_TABLE == "Table"
    assert PDTableAttributeObject().get_owner() == PDTableAttributeObject.OWNER_TABLE


def test_export_format_owner_constants_match_upstream() -> None:
    assert PDExportFormatAttributeObject.OWNER_XML_1_00 == "XML-1.00"
    assert PDExportFormatAttributeObject.OWNER_HTML_3_20 == "HTML-3.2"
    assert PDExportFormatAttributeObject.OWNER_HTML_4_01 == "HTML-4.01"
    assert PDExportFormatAttributeObject.OWNER_OEB_1_00 == "OEB-1.00"
    assert PDExportFormatAttributeObject.OWNER_RTF_1_05 == "RTF-1.05"
    assert PDExportFormatAttributeObject.OWNER_CSS_1_00 == "CSS-1.00"
    assert PDExportFormatAttributeObject.OWNER_CSS_2_00 == "CSS-2.00"


# ---------- upstream-parity dictionary-key constants ----------


def test_list_attribute_dictionary_key_constant() -> None:
    assert PDListAttributeObject.LIST_NUMBERING == "ListNumbering"


def test_print_field_dictionary_key_constants() -> None:
    assert PDPrintFieldAttributeObject.ROLE == "Role"
    assert PDPrintFieldAttributeObject.CHECKED == "checked"
    assert PDPrintFieldAttributeObject.DESC == "Desc"


def test_table_dictionary_key_constants() -> None:
    assert PDTableAttributeObject.ROW_SPAN == "RowSpan"
    assert PDTableAttributeObject.COL_SPAN == "ColSpan"
    assert PDTableAttributeObject.HEADERS == "Headers"
    assert PDTableAttributeObject.SCOPE == "Scope"
    assert PDTableAttributeObject.SUMMARY == "Summary"


# ---------- upstream-parity print field accessors ----------


def test_print_field_get_checked_state_default_off() -> None:
    obj = PDPrintFieldAttributeObject()
    assert obj.get_checked_state() == PDPrintFieldAttributeObject.CHECKED_STATE_OFF
    assert obj.get_checked_state() == "off"


def test_print_field_set_checked_state_round_trip_all_values() -> None:
    for state in (
        PDPrintFieldAttributeObject.CHECKED_STATE_ON,
        PDPrintFieldAttributeObject.CHECKED_STATE_OFF,
        PDPrintFieldAttributeObject.CHECKED_STATE_NEUTRAL,
    ):
        obj = PDPrintFieldAttributeObject()
        obj.set_checked_state(state)
        assert obj.get_checked_state() == state
        raw = obj.get_cos_object().get_dictionary_object("checked")
        assert isinstance(raw, COSName)
        assert raw.name == state


def test_print_field_alternate_name_round_trip() -> None:
    obj = PDPrintFieldAttributeObject()
    assert obj.get_alternate_name() is None
    obj.set_alternate_name("Submit button")
    assert obj.get_alternate_name() == "Submit button"
    # Cross-aliasing: the upstream-parity setter and the pypdfbox-style
    # getters must agree on the same /Desc entry.
    assert obj.get_desc() == "Submit button"
    assert obj.get_description() == "Submit button"


def test_print_field_alternate_name_none_or_empty_removes_entry() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_alternate_name("X")
    assert obj.get_cos_object().get_dictionary_object("Desc") is not None
    obj.set_alternate_name(None)
    assert obj.get_cos_object().get_dictionary_object("Desc") is None
    obj.set_alternate_name("Y")
    obj.set_alternate_name("")
    assert obj.get_cos_object().get_dictionary_object("Desc") is None


def test_print_field_role_constants_match_upstream() -> None:
    assert PDPrintFieldAttributeObject.ROLE_RB == "rb"
    assert PDPrintFieldAttributeObject.ROLE_CB == "cb"
    assert PDPrintFieldAttributeObject.ROLE_PB == "pb"
    assert PDPrintFieldAttributeObject.ROLE_TV == "tv"


def test_print_field_checked_state_constants_match_upstream() -> None:
    assert PDPrintFieldAttributeObject.CHECKED_STATE_ON == "on"
    assert PDPrintFieldAttributeObject.CHECKED_STATE_OFF == "off"
    assert PDPrintFieldAttributeObject.CHECKED_STATE_NEUTRAL == "neutral"


# ---------- upstream-parity inheritance for PDExportFormatAttributeObject ----------


def test_export_format_extends_layout() -> None:
    """Upstream: ``PDExportFormatAttributeObject extends PDLayoutAttributeObject``."""
    assert issubclass(PDExportFormatAttributeObject, PDLayoutAttributeObject)
    assert issubclass(PDExportFormatAttributeObject, PDStandardAttributeObject)


def test_export_format_inherits_layout_accessors() -> None:
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    # Should have the entire layout surface available because of the
    # upstream inheritance.
    obj.set_placement(PDLayoutAttributeObject.PLACEMENT_BLOCK)
    obj.set_writing_mode(PDLayoutAttributeObject.WRITING_MODE_LRTB)
    obj.set_space_before(3.5)
    obj.set_text_align(PDLayoutAttributeObject.TEXT_ALIGN_JUSTIFY)
    assert obj.get_placement() == "Block"
    assert obj.get_writing_mode() == "LrTb"
    assert obj.get_space_before() == 3.5
    assert obj.get_text_align() == "Justify"


def test_export_format_inherits_layout_color_helpers() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_color((0.5, 0.25, 0.75))
    obj.set_background_color((1.0, 0.0, 0.5))
    # COSFloat round-trips at 32-bit float precision; use exactly-
    # representable fractions to avoid float-comparison noise.
    assert obj.get_color() == (0.5, 0.25, 0.75)
    assert obj.get_background_color() == (1.0, 0.0, 0.5)


def test_export_format_owner_round_trip_via_constructor_owner_kwarg() -> None:
    for owner in (
        PDExportFormatAttributeObject.OWNER_XML_1_00,
        PDExportFormatAttributeObject.OWNER_HTML_3_20,
        PDExportFormatAttributeObject.OWNER_HTML_4_01,
        PDExportFormatAttributeObject.OWNER_OEB_1_00,
        PDExportFormatAttributeObject.OWNER_RTF_1_05,
        PDExportFormatAttributeObject.OWNER_CSS_1_00,
        PDExportFormatAttributeObject.OWNER_CSS_2_00,
    ):
        obj = PDExportFormatAttributeObject(owner=owner)
        assert obj.get_owner() == owner
