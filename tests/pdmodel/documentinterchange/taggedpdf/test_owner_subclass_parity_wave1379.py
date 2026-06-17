"""Wave 1379 — verification of the typed PDAttributeObject owner subclass
cluster flagged as a deferred follow-up.

The deferred entry (under ``pdmodel/font``) said
"Typed PDAttributeObject owner subclasses … Needs verification". This
module closes that audit by:

1. enumerating the public method surface of every upstream Java class in
   ``org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf`` and
   asserting that each has a snake_case counterpart on the corresponding
   pypdfbox class;
2. exercising every typed accessor end-to-end (set → get) so a regression
   would surface as a test failure rather than a silent parity drift.

No upstream JUnit test exists for these classes (the upstream test tree
only contains ``logicalstructure/PDStructureElementTest.java``), so the
coverage here is hand-written but anchored to the upstream public API
shape extracted from the Java sources.
"""

from __future__ import annotations

import re

import pytest

from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDExportFormatAttributeObject,
    PDLayoutAttributeObject,
    PDListAttributeObject,
    PDPrintFieldAttributeObject,
    PDTableAttributeObject,
)


def _camel_to_snake(name: str) -> str:
    """Convert ``camelCase`` / ``PascalCase`` to ``snake_case``."""
    # Insert underscore before any uppercase preceded by a lowercase letter
    # or by another uppercase + a lowercase (acronym boundary).
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# Upstream public method names per class — extracted directly from the
# PDFBox 3.0 Java sources at
# /tmp/pdfbox/pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/.
# Java overload sets collapse onto a single Python method, so duplicates
# (e.g. setSpaceBefore(float) / setSpaceBefore(int)) appear once below.
UPSTREAM_LAYOUT_METHODS = {
    "getPlacement", "setPlacement",
    "getWritingMode", "setWritingMode",
    "getBackgroundColor", "setBackgroundColor",
    "getBorderColors", "setAllBorderColors", "setBorderColors",
    "getBorderStyle", "setAllBorderStyles", "setBorderStyles",
    "getBorderThickness", "setAllBorderThicknesses", "setBorderThicknesses",
    "getPadding", "setAllPaddings", "setPaddings",
    "getColor", "setColor",
    "getSpaceBefore", "setSpaceBefore",
    "getSpaceAfter", "setSpaceAfter",
    "getStartIndent", "setStartIndent",
    "getEndIndent", "setEndIndent",
    "getTextIndent", "setTextIndent",
    "getTextAlign", "setTextAlign",
    "getBBox", "setBBox",
    "getWidth", "setWidth", "setWidthAuto",
    "getHeight", "setHeight", "setHeightAuto",
    "getBlockAlign", "setBlockAlign",
    "getInlineAlign", "setInlineAlign",
    "getTBorderStyle", "setAllTBorderStyles", "setTBorderStyles",
    "getTPadding", "setAllTPaddings", "setTPaddings",
    "getBaselineShift", "setBaselineShift",
    "getLineHeight", "setLineHeight", "setLineHeightNormal", "setLineHeightAuto",
    "getTextDecorationColor", "setTextDecorationColor",
    "getTextDecorationThickness", "setTextDecorationThickness",
    "getTextDecorationType", "setTextDecorationType",
    "getRubyAlign", "setRubyAlign",
    "getRubyPosition", "setRubyPosition",
    "getGlyphOrientationVertical", "setGlyphOrientationVertical",
    "getColumnCount", "setColumnCount",
    "getColumnGap", "setColumnGap", "setColumnGaps",
    "getColumnWidths", "setAllColumnWidths", "setColumnWidths",
}

UPSTREAM_LIST_METHODS = {"getListNumbering", "setListNumbering"}

UPSTREAM_PRINT_FIELD_METHODS = {
    "getRole", "setRole",
    "getCheckedState", "setCheckedState",
    "getAlternateName", "setAlternateName",
}

UPSTREAM_TABLE_METHODS = {
    "getRowSpan", "setRowSpan",
    "getColSpan", "setColSpan",
    "getHeaders", "setHeaders",
    "getScope", "setScope",
    "getSummary", "setSummary",
}

# ExportFormat extends Layout and overlays the table/list cross-cut methods.
UPSTREAM_EXPORT_FORMAT_METHODS = (
    UPSTREAM_LAYOUT_METHODS
    | {"getListNumbering", "setListNumbering"}
    | UPSTREAM_TABLE_METHODS
)


def _assert_parity(cls: type, upstream_methods: set[str]) -> None:
    missing: list[str] = []
    for camel in upstream_methods:
        snake = _camel_to_snake(camel)
        if not hasattr(cls, snake):
            missing.append(f"{camel} -> {snake}")
    assert not missing, (
        f"{cls.__name__} missing snake_case ports for upstream methods: {missing}"
    )


# ---------------------------------------------------------------------------
# Method-surface parity audit
# ---------------------------------------------------------------------------


def test_layout_attribute_object_method_parity() -> None:
    _assert_parity(PDLayoutAttributeObject, UPSTREAM_LAYOUT_METHODS)


def test_list_attribute_object_method_parity() -> None:
    _assert_parity(PDListAttributeObject, UPSTREAM_LIST_METHODS)


def test_print_field_attribute_object_method_parity() -> None:
    _assert_parity(PDPrintFieldAttributeObject, UPSTREAM_PRINT_FIELD_METHODS)


def test_table_attribute_object_method_parity() -> None:
    _assert_parity(PDTableAttributeObject, UPSTREAM_TABLE_METHODS)


def test_export_format_attribute_object_method_parity() -> None:
    _assert_parity(PDExportFormatAttributeObject, UPSTREAM_EXPORT_FORMAT_METHODS)


# ---------------------------------------------------------------------------
# Owner constants — upstream-parity public statics
# ---------------------------------------------------------------------------


def test_layout_owner_constant() -> None:
    assert PDLayoutAttributeObject.OWNER_LAYOUT == "Layout"
    obj = PDLayoutAttributeObject()
    assert obj.get_owner() == "Layout"


def test_list_owner_constant() -> None:
    assert PDListAttributeObject.OWNER_LIST == "List"
    obj = PDListAttributeObject()
    assert obj.get_owner() == "List"


def test_print_field_owner_constant() -> None:
    assert PDPrintFieldAttributeObject.OWNER_PRINT_FIELD == "PrintField"
    obj = PDPrintFieldAttributeObject()
    assert obj.get_owner() == "PrintField"


def test_table_owner_constant() -> None:
    assert PDTableAttributeObject.OWNER_TABLE == "Table"
    obj = PDTableAttributeObject()
    assert obj.get_owner() == "Table"


def test_export_format_owner_constants() -> None:
    # All seven owner names per PDF 32000-1:2008 §14.8.5.2.
    assert PDExportFormatAttributeObject.OWNER_XML_1_00 == "XML-1.00"
    assert PDExportFormatAttributeObject.OWNER_HTML_3_20 == "HTML-3.2"
    assert PDExportFormatAttributeObject.OWNER_HTML_4_01 == "HTML-4.01"
    assert PDExportFormatAttributeObject.OWNER_OEB_1_00 == "OEB-1.00"
    assert PDExportFormatAttributeObject.OWNER_RTF_1_05 == "RTF-1.05"
    assert PDExportFormatAttributeObject.OWNER_CSS_1_00 == "CSS-1.00"
    assert PDExportFormatAttributeObject.OWNER_CSS_2_00 == "CSS-2.00"


# ---------------------------------------------------------------------------
# Layout — round-trip every typed accessor
# ---------------------------------------------------------------------------


def test_layout_round_trip_scalars() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_placement(PDLayoutAttributeObject.PLACEMENT_BLOCK)
    obj.set_writing_mode(PDLayoutAttributeObject.WRITING_MODE_RLTB)
    obj.set_space_before(3.5)
    obj.set_space_after(4.5)
    obj.set_start_indent(1.0)
    obj.set_end_indent(2.0)
    obj.set_text_indent(0.5)
    obj.set_text_align(PDLayoutAttributeObject.TEXT_ALIGN_JUSTIFY)
    obj.set_baseline_shift(0.25)
    obj.set_column_count(3)
    obj.set_block_align(PDLayoutAttributeObject.BLOCK_ALIGN_MIDDLE)
    obj.set_inline_align(PDLayoutAttributeObject.INLINE_ALIGN_CENTER)
    obj.set_ruby_align(PDLayoutAttributeObject.RUBY_ALIGN_DISTRIBUTE)
    obj.set_ruby_position(PDLayoutAttributeObject.RUBY_POSITION_AFTER)
    obj.set_glyph_orientation_vertical(
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_90_DEGREES
    )
    obj.set_text_decoration_type(
        PDLayoutAttributeObject.TEXT_DECORATION_TYPE_UNDERLINE
    )
    obj.set_text_decoration_thickness(1.5)

    assert obj.get_placement() == "Block"
    assert obj.get_writing_mode() == "RlTb"
    assert obj.get_space_before() == 3.5
    assert obj.get_space_after() == 4.5
    assert obj.get_start_indent() == 1.0
    assert obj.get_end_indent() == 2.0
    assert obj.get_text_indent() == 0.5
    assert obj.get_text_align() == "Justify"
    assert obj.get_baseline_shift() == 0.25
    assert obj.get_column_count() == 3
    assert obj.get_block_align() == "Middle"
    assert obj.get_inline_align() == "Center"
    assert obj.get_ruby_align() == "Distribute"
    assert obj.get_ruby_position() == "After"
    assert obj.get_glyph_orientation_vertical() == "90"
    assert obj.get_text_decoration_type() == "Underline"
    assert obj.get_text_decoration_thickness() == 1.5


def test_layout_defaults_match_upstream() -> None:
    obj = PDLayoutAttributeObject()
    # Upstream documented defaults.
    assert obj.get_placement() == "Inline"
    assert obj.get_writing_mode() == "LrTb"
    assert obj.get_text_align() == "Start"
    assert obj.get_block_align() == "Before"
    assert obj.get_inline_align() == "Start"
    assert obj.get_ruby_align() == "Distribute"
    assert obj.get_ruby_position() == "Before"
    assert obj.get_glyph_orientation_vertical() == "Auto"
    assert obj.get_text_decoration_type() == "None"
    assert obj.get_column_count() == 1
    assert obj.get_space_before() == 0.0
    assert obj.get_space_after() == 0.0
    assert obj.get_start_indent() == 0.0
    assert obj.get_end_indent() == 0.0
    assert obj.get_text_indent() == 0.0
    assert obj.get_baseline_shift() == 0.0
    assert obj.get_width() == "Auto"
    assert obj.get_height() == "Auto"
    assert obj.get_line_height() == "Normal"


def test_layout_polymorphic_setters() -> None:
    obj = PDLayoutAttributeObject()
    # BorderStyle as a single name vs per-side array.
    obj.set_all_border_styles(PDLayoutAttributeObject.BORDER_STYLE_SOLID)
    assert obj.get_border_style() == "Solid"
    obj.set_border_styles(["Dotted", "Dashed", "Solid", "Double"])
    assert obj.get_border_style() == ["Dotted", "Dashed", "Solid", "Double"]
    # BorderThickness scalar vs array.
    obj.set_all_border_thicknesses(2.0)
    assert obj.get_border_thickness() == 2.0
    obj.set_border_thicknesses([1.0, 2.0, 3.0, 4.0])
    assert obj.get_border_thickness() == [1.0, 2.0, 3.0, 4.0]
    # Padding scalar vs array.
    obj.set_all_paddings(5.0)
    assert obj.get_padding() == 5.0
    obj.set_paddings([1.5, 2.5, 3.5, 4.5])
    assert obj.get_padding() == [1.5, 2.5, 3.5, 4.5]
    # TBorderStyle / TPadding parity with their non-T counterparts.
    obj.set_all_t_border_styles(PDLayoutAttributeObject.BORDER_STYLE_GROOVE)
    assert obj.get_t_border_style() == "Groove"
    obj.set_t_paddings([0.5, 1.5, 2.5, 3.5])
    assert obj.get_t_padding() == [0.5, 1.5, 2.5, 3.5]
    # ColumnGap / ColumnWidths.
    obj.set_all_column_gaps(2.0)
    assert obj.get_column_gap() == 2.0
    obj.set_column_gaps([1.0, 2.0, 3.0])
    assert obj.get_column_gap() == [1.0, 2.0, 3.0]
    obj.set_all_column_widths(10.0)
    assert obj.get_column_widths() == 10.0
    obj.set_column_widths([8.0, 9.0, 10.0])
    assert obj.get_column_widths() == [8.0, 9.0, 10.0]


def test_layout_width_height_auto_and_numeric() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_width_auto()
    assert obj.get_width() == "Auto"
    obj.set_width(120.0)
    assert obj.get_width() == 120.0
    obj.set_height_auto()
    assert obj.get_height() == "Auto"
    obj.set_height(50.0)
    assert obj.get_height() == 50.0


def test_layout_line_height_polymorphic() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_line_height_normal()
    assert obj.get_line_height() == "Normal"
    obj.set_line_height_auto()
    assert obj.get_line_height() == "Auto"
    obj.set_line_height(14.0)
    assert obj.get_line_height() == 14.0


def test_layout_bbox_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_b_box((1.0, 2.0, 3.0, 4.0))
    assert obj.get_b_box() == (1.0, 2.0, 3.0, 4.0)
    obj.set_b_box(None)
    assert obj.get_b_box() is None
    with pytest.raises(ValueError):
        obj.set_b_box((1.0, 2.0, 3.0))  # type: ignore[arg-type]


def test_layout_color_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    # Values chosen to round-trip exactly through 32-bit float (powers of 2).
    obj.set_background_color((0.5, 0.25, 0.125))
    assert obj.get_background_color() == pytest.approx((0.5, 0.25, 0.125))
    obj.set_color((0.5, 1.0, 0.0))
    assert obj.get_color() == pytest.approx((0.5, 1.0, 0.0))
    obj.set_text_decoration_color((0.75, 0.5, 0.25))
    assert obj.get_text_decoration_color() == pytest.approx((0.75, 0.5, 0.25))
    obj.set_all_border_colors((0.0, 0.0, 0.0))
    assert obj.get_border_colors() == pytest.approx((0.0, 0.0, 0.0))


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_round_trip_all_numberings() -> None:
    obj = PDListAttributeObject()
    for value in (
        PDListAttributeObject.LIST_NUMBERING_NONE,
        PDListAttributeObject.LIST_NUMBERING_DISC,
        PDListAttributeObject.LIST_NUMBERING_CIRCLE,
        PDListAttributeObject.LIST_NUMBERING_SQUARE,
        PDListAttributeObject.LIST_NUMBERING_DECIMAL,
        PDListAttributeObject.LIST_NUMBERING_UPPER_ROMAN,
        PDListAttributeObject.LIST_NUMBERING_LOWER_ROMAN,
        PDListAttributeObject.LIST_NUMBERING_UPPER_ALPHA,
        PDListAttributeObject.LIST_NUMBERING_LOWER_ALPHA,
    ):
        obj.set_list_numbering(value)
        assert obj.get_list_numbering() == value


def test_list_default_is_none() -> None:
    obj = PDListAttributeObject()
    assert obj.get_list_numbering() == "None"


# ---------------------------------------------------------------------------
# PrintField
# ---------------------------------------------------------------------------


def test_print_field_role_and_checked_state() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_role(PDPrintFieldAttributeObject.ROLE_CB)
    assert obj.get_role() == "cb"
    # Default checked state per upstream is "off".
    assert obj.get_checked_state() == "off"
    obj.set_checked_state(PDPrintFieldAttributeObject.CHECKED_STATE_ON)
    assert obj.get_checked_state() == "on"
    obj.set_checked_state(PDPrintFieldAttributeObject.CHECKED_STATE_NEUTRAL)
    assert obj.get_checked_state() == "neutral"


def test_print_field_alternate_name_round_trip() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_alternate_name("Signature field")
    assert obj.get_alternate_name() == "Signature field"
    obj.set_alternate_name(None)
    assert obj.get_alternate_name() is None


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


def test_table_spans_and_scope() -> None:
    obj = PDTableAttributeObject()
    assert obj.get_row_span() == 1
    assert obj.get_col_span() == 1
    obj.set_row_span(3)
    obj.set_col_span(2)
    obj.set_scope(PDTableAttributeObject.SCOPE_BOTH)
    obj.set_summary("Quarterly numbers")
    assert obj.get_row_span() == 3
    assert obj.get_col_span() == 2
    assert obj.get_scope() == "Both"
    assert obj.get_summary() == "Quarterly numbers"


def test_table_headers_round_trip() -> None:
    obj = PDTableAttributeObject()
    obj.set_headers(["h1", "h2", "h3"])
    assert obj.get_headers() == ["h1", "h2", "h3"]
    obj.set_headers([])
    assert obj.get_headers() == []


# ---------------------------------------------------------------------------
# ExportFormat — extends Layout + overlays List/Table cross-cuts
# ---------------------------------------------------------------------------


def test_export_format_inherits_layout_setters() -> None:
    obj = PDExportFormatAttributeObject(
        owner=PDExportFormatAttributeObject.OWNER_HTML_4_01
    )
    obj.set_placement(PDLayoutAttributeObject.PLACEMENT_BLOCK)
    obj.set_text_align(PDLayoutAttributeObject.TEXT_ALIGN_JUSTIFY)
    obj.set_column_count(4)
    # Cross-cut from List + Table.
    obj.set_list_numbering(PDListAttributeObject.LIST_NUMBERING_DECIMAL)
    obj.set_row_span(2)
    obj.set_col_span(3)
    obj.set_headers(["a", "b"])
    obj.set_scope(PDTableAttributeObject.SCOPE_COLUMN)
    obj.set_summary("note")

    assert obj.get_owner() == "HTML-4.01"
    assert obj.get_placement() == "Block"
    assert obj.get_text_align() == "Justify"
    assert obj.get_column_count() == 4
    assert obj.get_list_numbering() == "Decimal"
    assert obj.get_row_span() == 2
    assert obj.get_col_span() == 3
    assert obj.get_headers() == ["a", "b"]
    assert obj.get_scope() == "Column"
    assert obj.get_summary() == "note"


def test_export_format_is_valid_owner_predicate() -> None:
    assert PDExportFormatAttributeObject.is_valid_owner("XML-1.00")
    assert PDExportFormatAttributeObject.is_valid_owner("CSS-2.00")
    assert not PDExportFormatAttributeObject.is_valid_owner("Layout")
    assert not PDExportFormatAttributeObject.is_valid_owner(None)


# ---------------------------------------------------------------------------
# Stringification — upstream toString shape
# ---------------------------------------------------------------------------


def test_layout_to_string_includes_specified_keys_only() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_placement(PDLayoutAttributeObject.PLACEMENT_BLOCK)
    obj.set_text_align(PDLayoutAttributeObject.TEXT_ALIGN_CENTER)
    s = str(obj)
    assert "Placement=Block" in s
    assert "TextAlign=Center" in s
    # Unspecified entries must not appear.
    assert "WritingMode=" not in s
    assert "ColumnCount=" not in s


def test_table_to_string_includes_specified_keys_only() -> None:
    obj = PDTableAttributeObject()
    obj.set_row_span(2)
    obj.set_headers(["h1", "h2"])
    s = str(obj)
    assert "RowSpan=2" in s
    # Headers rendered via array_to_string ("[h1, h2]").
    assert "Headers=[h1, h2]" in s
    assert "ColSpan=" not in s
    assert "Scope=" not in s


def test_list_to_string_omits_unspecified() -> None:
    obj = PDListAttributeObject()
    base = str(obj)
    assert "ListNumbering=" not in base
    obj.set_list_numbering(PDListAttributeObject.LIST_NUMBERING_DECIMAL)
    assert "ListNumbering=Decimal" in str(obj)
