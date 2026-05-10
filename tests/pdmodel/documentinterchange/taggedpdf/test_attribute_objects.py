from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDExportFormatAttributeObject,
    PDFourColours,
    PDLayoutAttributeObject,
    PDListAttributeObject,
    PDPrintFieldAttributeObject,
    PDStandardAttributeObject,
    PDTableAttributeObject,
    PDUserAttributeObject,
)

# ---------- owner identity ----------


def test_layout_owner() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_owner() == "Layout"


def test_list_owner() -> None:
    obj = PDListAttributeObject()
    assert obj.get_owner() == "List"


def test_print_field_owner() -> None:
    obj = PDPrintFieldAttributeObject()
    assert obj.get_owner() == "PrintField"


def test_table_owner() -> None:
    obj = PDTableAttributeObject()
    assert obj.get_owner() == "Table"


def test_export_format_owner_default() -> None:
    obj = PDExportFormatAttributeObject()
    assert obj.get_owner() == "XML-1.00"


def test_export_format_owner_custom() -> None:
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    assert obj.get_owner() == "HTML-4.01"


def test_user_owner() -> None:
    obj = PDUserAttributeObject()
    assert obj.get_owner() == "UserProperties"


# ---------- typed accessor round trips ----------


def test_layout_round_trip_placement_and_writing_mode() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_placement("Block")
    obj.set_writing_mode("LrTb")
    assert obj.get_placement() == "Block"
    assert obj.get_writing_mode() == "LrTb"


def test_layout_space_before_after() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_space_before(3.5)
    obj.set_space_after(2)
    assert obj.get_space_before() == 3.5
    assert obj.get_space_after() == 2.0


def test_layout_start_indent_default_zero_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_start_indent() == 0.0
    obj.set_start_indent(12.5)
    assert obj.get_start_indent() == 12.5


def test_layout_end_indent_default_zero_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_end_indent() == 0.0
    obj.set_end_indent(7)
    assert obj.get_end_indent() == 7.0


def test_layout_text_indent_default_zero_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_text_indent() == 0.0
    obj.set_text_indent(-4.0)
    assert obj.get_text_indent() == -4.0


def test_layout_text_align_default_start_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_text_align() == PDLayoutAttributeObject.TEXT_ALIGN_START
    obj.set_text_align(PDLayoutAttributeObject.TEXT_ALIGN_JUSTIFY)
    assert obj.get_text_align() == "Justify"


def test_layout_baseline_shift_default_zero_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_baseline_shift() == 0.0
    obj.set_baseline_shift(2.25)
    assert obj.get_baseline_shift() == 2.25


def test_list_round_trip_list_numbering() -> None:
    obj = PDListAttributeObject()
    obj.set_list_numbering("Decimal")
    assert obj.get_list_numbering() == "Decimal"


def test_list_numbering_default_is_none_when_absent() -> None:
    obj = PDListAttributeObject()
    assert obj.get_list_numbering() == PDListAttributeObject.LIST_NUMBERING_NONE
    assert obj.get_list_numbering() == "None"


def test_list_numbering_round_trip_all_non_default_values() -> None:
    non_default_values = [
        PDListAttributeObject.LIST_NUMBERING_DISC,
        PDListAttributeObject.LIST_NUMBERING_CIRCLE,
        PDListAttributeObject.LIST_NUMBERING_SQUARE,
        PDListAttributeObject.LIST_NUMBERING_DECIMAL,
        PDListAttributeObject.LIST_NUMBERING_UPPER_ROMAN,
        PDListAttributeObject.LIST_NUMBERING_LOWER_ROMAN,
        PDListAttributeObject.LIST_NUMBERING_UPPER_ALPHA,
        PDListAttributeObject.LIST_NUMBERING_LOWER_ALPHA,
    ]
    for value in non_default_values:
        obj = PDListAttributeObject()
        obj.set_list_numbering(value)
        assert obj.get_list_numbering() == value


def test_list_numbering_writes_cos_name() -> None:
    obj = PDListAttributeObject()
    obj.set_list_numbering(PDListAttributeObject.LIST_NUMBERING_DECIMAL)
    raw = obj.get_cos_object().get_dictionary_object("ListNumbering")
    assert isinstance(raw, COSName)
    assert raw.name == "Decimal"


def test_print_field_round_trip_role() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_role("rb")
    assert obj.get_role() == "rb"


def test_print_field_checked_and_desc() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_checked("on")
    obj.set_desc("a checkbox")
    assert obj.get_checked() == "on"
    assert obj.get_desc() == "a checkbox"


def test_table_round_trip_spans() -> None:
    obj = PDTableAttributeObject()
    obj.set_row_span(2)
    obj.set_col_span(3)
    assert obj.get_row_span() == 2
    assert obj.get_col_span() == 3


def test_table_scope_summary_headers() -> None:
    obj = PDTableAttributeObject()
    obj.set_scope("Row")
    obj.set_summary("financials")
    obj.set_headers(["h1", "h2"])
    assert obj.get_scope() == "Row"
    assert obj.get_summary() == "financials"
    assert obj.get_headers() == ["h1", "h2"]


def test_table_defaults_when_absent() -> None:
    obj = PDTableAttributeObject()
    assert obj.get_row_span() == 1
    assert obj.get_col_span() == 1
    assert obj.get_headers() == []
    assert obj.get_scope() is None
    assert obj.get_summary() is None


def test_table_row_col_span_round_trip_non_default() -> None:
    obj = PDTableAttributeObject()
    obj.set_row_span(4)
    obj.set_col_span(7)
    assert obj.get_row_span() == 4
    assert obj.get_col_span() == 7


def test_table_summary_round_trip_non_default() -> None:
    obj = PDTableAttributeObject()
    obj.set_summary("quarterly results")
    assert obj.get_summary() == "quarterly results"


def test_table_headers_round_trip_non_default() -> None:
    obj = PDTableAttributeObject()
    obj.set_headers(["alpha", "beta", "gamma"])
    assert obj.get_headers() == ["alpha", "beta", "gamma"]


def test_table_set_headers_empty_removes_entry() -> None:
    obj = PDTableAttributeObject()
    obj.set_headers(["x", "y"])
    assert obj.get_cos_object().get_dictionary_object("Headers") is not None
    obj.set_headers([])
    assert obj.get_cos_object().get_dictionary_object("Headers") is None
    assert obj.get_headers() == []


def test_table_set_scope_writes_cos_name() -> None:
    obj = PDTableAttributeObject()
    obj.set_scope(PDTableAttributeObject.SCOPE_ROW)
    raw = obj.get_cos_object().get_dictionary_object("Scope")
    assert isinstance(raw, COSName)
    assert raw.name == "Row"


def test_table_scope_constants_round_trip() -> None:
    for scope in (
        PDTableAttributeObject.SCOPE_ROW,
        PDTableAttributeObject.SCOPE_COLUMN,
        PDTableAttributeObject.SCOPE_BOTH,
    ):
        obj = PDTableAttributeObject()
        obj.set_scope(scope)
        assert obj.get_scope() == scope


def test_table_get_headers_decodes_utf8_cos_string() -> None:
    obj = PDTableAttributeObject()
    array = COSArray()
    array.add(COSString("café".encode("utf-8")))
    obj.get_cos_object().set_item("Headers", array)
    assert obj.get_headers() == ["café"]


def test_user_set_and_get_property() -> None:
    obj = PDUserAttributeObject()
    obj.set_property("alpha", 42)
    obj.set_property("beta", "hello", format="text", hidden=True)
    props = obj.get_property()
    assert len(props) == 2
    assert props[0] == {"N": "alpha", "V": 42, "F": None, "H": False}
    assert props[1] == {"N": "beta", "V": "hello", "F": "text", "H": True}


# ---------- PDStandardAttributeObject helpers ----------


def test_is_specified_reports_presence() -> None:
    obj = PDLayoutAttributeObject()
    assert not obj.is_specified("Placement")
    obj.set_placement("Block")
    assert obj.is_specified("Placement")


def test_standard_is_abstract_intermediate() -> None:
    # Sanity: subclasses inherit from the standard intermediate.
    assert issubclass(PDLayoutAttributeObject, PDStandardAttributeObject)
    assert issubclass(PDUserAttributeObject, PDStandardAttributeObject)


# ---------- PDFourColours + Layout color helpers ----------


def test_four_colours_round_trip_distinct_sides() -> None:
    four = PDFourColours()
    four.set_top((1.0, 0.0, 0.0))
    four.set_right((0.0, 1.0, 0.0))
    four.set_bottom((0.0, 0.0, 1.0))
    four.set_left((0.5, 0.5, 0.5))
    assert four.get_top() == (1.0, 0.0, 0.0)
    assert four.get_right() == (0.0, 1.0, 0.0)
    assert four.get_bottom() == (0.0, 0.0, 1.0)
    assert four.get_left() == (0.5, 0.5, 0.5)


def test_four_colours_single_color_applies_to_all_sides() -> None:
    four = PDFourColours.single_color((0.5, 0.5, 0.5))
    assert four.get_top() == (0.5, 0.5, 0.5)
    assert four.get_right() == (0.5, 0.5, 0.5)
    assert four.get_bottom() == (0.5, 0.5, 0.5)
    assert four.get_left() == (0.5, 0.5, 0.5)


def test_layout_background_color_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_background_color((1.0, 0.5, 0.0))
    assert obj.get_background_color() == (1.0, 0.5, 0.0)


def test_layout_color_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_color((0.25, 0.5, 0.75))
    assert obj.get_color() == (0.25, 0.5, 0.75)


def test_layout_border_color_round_trip_with_four_colours() -> None:
    obj = PDLayoutAttributeObject()
    four = PDFourColours()
    four.set_top((1.0, 0.0, 0.0))
    four.set_right((0.0, 1.0, 0.0))
    four.set_bottom((0.0, 0.0, 1.0))
    four.set_left((0.0, 0.0, 0.0))
    obj.set_border_color(four)
    read_back = obj.get_border_color()
    assert read_back is not None
    assert read_back.get_top() == (1.0, 0.0, 0.0)
    assert read_back.get_right() == (0.0, 1.0, 0.0)
    assert read_back.get_bottom() == (0.0, 0.0, 1.0)
    assert read_back.get_left() == (0.0, 0.0, 0.0)


# Factory dispatch tests are deferred: they require the wiring update to
# pd_attribute_object.py::create() described in the task report. Once the
# /O dispatch is applied, add tests asserting Layout/List/UserProperties/
# XML-1.00 each map to their concrete subclass and unknown owners fall
# back to the generic PDAttributeObject.
