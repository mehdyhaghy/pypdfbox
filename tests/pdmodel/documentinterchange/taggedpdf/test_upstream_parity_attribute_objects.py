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


def test_layout_owner_constant_is_owner_layout() -> None:
    assert PDLayoutAttributeObject.OWNER_LAYOUT == "Layout"
    assert PDLayoutAttributeObject().get_owner() == PDLayoutAttributeObject.OWNER_LAYOUT


def test_layout_round_out_value_constants_match_upstream() -> None:
    cls = PDLayoutAttributeObject
    # LineHeight sentinels.
    assert cls.LINE_HEIGHT_NORMAL == "Normal"
    assert cls.LINE_HEIGHT_AUTO == "Auto"
    # TextDecorationType.
    assert cls.TEXT_DECORATION_TYPE_NONE == "None"
    assert cls.TEXT_DECORATION_TYPE_UNDERLINE == "Underline"
    assert cls.TEXT_DECORATION_TYPE_OVERLINE == "Overline"
    assert cls.TEXT_DECORATION_TYPE_LINE_THROUGH == "LineThrough"
    # RubyAlign.
    assert cls.RUBY_ALIGN_START == "Start"
    assert cls.RUBY_ALIGN_CENTER == "Center"
    assert cls.RUBY_ALIGN_END == "End"
    assert cls.RUBY_ALIGN_JUSTIFY == "Justify"
    assert cls.RUBY_ALIGN_DISTRIBUTE == "Distribute"
    # RubyPosition.
    assert cls.RUBY_POSITION_BEFORE == "Before"
    assert cls.RUBY_POSITION_AFTER == "After"
    assert cls.RUBY_POSITION_WARICHU == "Warichu"
    assert cls.RUBY_POSITION_INLINE == "Inline"
    # GlyphOrientationVertical.
    assert cls.GLYPH_ORIENTATION_VERTICAL_AUTO == "Auto"
    assert cls.GLYPH_ORIENTATION_VERTICAL_MINUS_180_DEGREES == "-180"
    assert cls.GLYPH_ORIENTATION_VERTICAL_MINUS_90_DEGREES == "-90"
    assert cls.GLYPH_ORIENTATION_VERTICAL_ZERO_DEGREES == "0"
    assert cls.GLYPH_ORIENTATION_VERTICAL_90_DEGREES == "90"
    assert cls.GLYPH_ORIENTATION_VERTICAL_180_DEGREES == "180"
    assert cls.GLYPH_ORIENTATION_VERTICAL_270_DEGREES == "270"
    assert cls.GLYPH_ORIENTATION_VERTICAL_360_DEGREES == "360"


def test_export_format_inherits_round_out_layout_accessors() -> None:
    """Round-out layout accessors must be reachable through the export-format
    subclass (upstream inheritance)."""
    obj = PDExportFormatAttributeObject()
    obj.set_t_padding([1.0, 2.0, 3.0, 4.0])
    obj.set_line_height_auto()
    obj.set_text_decoration_type(
        PDLayoutAttributeObject.TEXT_DECORATION_TYPE_UNDERLINE
    )
    obj.set_ruby_align(PDLayoutAttributeObject.RUBY_ALIGN_JUSTIFY)
    obj.set_ruby_position(PDLayoutAttributeObject.RUBY_POSITION_WARICHU)
    obj.set_glyph_orientation_vertical(
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_90_DEGREES
    )
    assert obj.get_t_padding() == [1.0, 2.0, 3.0, 4.0]
    assert obj.get_line_height() == "Auto"
    assert obj.get_text_decoration_type() == "Underline"
    assert obj.get_ruby_align() == "Justify"
    assert obj.get_ruby_position() == "Warichu"
    assert obj.get_glyph_orientation_vertical() == "90"


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


# ---------- upstream-parity __str__ / toString ----------


def test_pd_attribute_object_str_matches_upstream_owner_only() -> None:
    """Upstream ``PDAttributeObject.toString()`` returns ``"O=" + owner``."""
    # Use a concrete subclass with no extra entries set; PDListAttributeObject's
    # __str__ falls through to the base when ListNumbering is unspecified.
    obj = PDListAttributeObject()
    assert str(obj) == "O=List"


def test_pd_list_attribute_object_str_appends_list_numbering_when_specified() -> None:
    """Upstream ``PDListAttributeObject.toString()`` appends
    ``", ListNumbering=<value>"`` when the entry is specified."""
    obj = PDListAttributeObject()
    # Default: no ListNumbering written, so __str__ stays at the owner level.
    assert str(obj) == "O=List"
    obj.set_list_numbering(PDListAttributeObject.LIST_NUMBERING_DECIMAL)
    assert str(obj) == "O=List, ListNumbering=Decimal"


def test_pd_print_field_str_appends_specified_entries_in_upstream_order() -> None:
    """Upstream ``PDPrintFieldAttributeObject.toString()`` appends
    Role/Checked/Desc in that order, only when each is specified."""
    obj = PDPrintFieldAttributeObject()
    assert str(obj) == "O=PrintField"
    obj.set_role(PDPrintFieldAttributeObject.ROLE_RB)
    assert str(obj) == "O=PrintField, Role=rb"
    obj.set_checked_state(PDPrintFieldAttributeObject.CHECKED_STATE_ON)
    assert str(obj) == "O=PrintField, Role=rb, Checked=on"
    obj.set_alternate_name("Submit")
    assert str(obj) == "O=PrintField, Role=rb, Checked=on, Desc=Submit"


def test_pd_print_field_str_skips_unset_entries() -> None:
    """Only specified entries are appended; ordering follows upstream."""
    obj = PDPrintFieldAttributeObject()
    obj.set_alternate_name("just-desc")
    assert str(obj) == "O=PrintField, Desc=just-desc"
    obj2 = PDPrintFieldAttributeObject()
    obj2.set_checked_state(PDPrintFieldAttributeObject.CHECKED_STATE_NEUTRAL)
    assert str(obj2) == "O=PrintField, Checked=neutral"


def test_pd_attribute_object_array_to_string_matches_upstream_format() -> None:
    """Upstream ``PDAttributeObject.arrayToString(...)`` formats sequences as
    ``"[a, b, c]"`` via ``StringJoiner(", ", "[", "]")``."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDAttributeObject,
    )

    assert PDAttributeObject.array_to_string([]) == "[]"
    assert PDAttributeObject.array_to_string(["a"]) == "[a]"
    assert PDAttributeObject.array_to_string(["a", "b", "c"]) == "[a, b, c]"
    # float array path on upstream renders Float.toString — Python's str(float)
    # collapses 1.0 to "1.0" too, so the visible output matches.
    assert PDAttributeObject.array_to_string([1.0, 2.5, 3.0]) == "[1.0, 2.5, 3.0]"
    assert PDAttributeObject.array_to_string((4, 5, 6)) == "[4, 5, 6]"
