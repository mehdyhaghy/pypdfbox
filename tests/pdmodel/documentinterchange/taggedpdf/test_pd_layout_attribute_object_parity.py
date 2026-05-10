"""Parity coverage for the PDLayoutAttributeObject accessors added to round
out the §14.8.5.4 typed surface.

The legacy ``placement / writing_mode / *_indent / *color / baseline_shift``
accessors are exercised in ``test_attribute_objects.py``; this module only
covers the newer wave (b_box, block_align, border_colors, border_style,
border_thickness, column_count, column_gap, padding, inline_align, height,
width, writing_mode constants).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDFourColours,
    PDLayoutAttributeObject,
)

# ---------- /BBox ----------


def test_b_box_default_is_none_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_b_box() is None


def test_b_box_round_trip_writes_four_element_array() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_b_box((10.0, 20.0, 110.5, 220.5))
    assert obj.get_b_box() == (10.0, 20.0, 110.5, 220.5)
    raw = obj.get_cos_object().get_dictionary_object("BBox")
    assert isinstance(raw, COSArray)
    assert raw.size() == 4


def test_b_box_set_none_removes_entry() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_b_box((0.0, 0.0, 1.0, 1.0))
    assert obj.get_cos_object().get_dictionary_object("BBox") is not None
    obj.set_b_box(None)
    assert obj.get_cos_object().get_dictionary_object("BBox") is None
    assert obj.get_b_box() is None


def test_b_box_rejects_wrong_arity() -> None:
    obj = PDLayoutAttributeObject()
    with pytest.raises(ValueError):
        obj.set_b_box((1.0, 2.0, 3.0))  # type: ignore[arg-type]


# ---------- /BlockAlign ----------


def test_block_align_default_before_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_block_align() == PDLayoutAttributeObject.BLOCK_ALIGN_BEFORE
    assert obj.get_block_align() == "Before"
    obj.set_block_align(PDLayoutAttributeObject.BLOCK_ALIGN_MIDDLE)
    assert obj.get_block_align() == "Middle"
    obj.set_block_align(PDLayoutAttributeObject.BLOCK_ALIGN_AFTER)
    assert obj.get_block_align() == "After"
    obj.set_block_align(PDLayoutAttributeObject.BLOCK_ALIGN_JUSTIFY)
    assert obj.get_block_align() == "Justify"
    raw = obj.get_cos_object().get_dictionary_object("BlockAlign")
    assert isinstance(raw, COSName)


# ---------- /InlineAlign ----------


def test_inline_align_default_start_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_inline_align() == PDLayoutAttributeObject.INLINE_ALIGN_START
    obj.set_inline_align(PDLayoutAttributeObject.INLINE_ALIGN_CENTER)
    assert obj.get_inline_align() == "Center"
    obj.set_inline_align(PDLayoutAttributeObject.INLINE_ALIGN_END)
    assert obj.get_inline_align() == "End"


# ---------- /BorderColor (polymorphic getter via get_border_colors) ----------


def test_border_colors_returns_pd_four_colours_for_four_slot_array() -> None:
    obj = PDLayoutAttributeObject()
    four = PDFourColours()
    four.set_top((1.0, 0.0, 0.0))
    four.set_right((0.0, 1.0, 0.0))
    four.set_bottom((0.0, 0.0, 1.0))
    four.set_left((0.5, 0.5, 0.5))
    obj.set_border_colors(four)
    out = obj.get_border_colors()
    assert isinstance(out, PDFourColours)
    assert out.get_top() == (1.0, 0.0, 0.0)
    assert out.get_left() == (0.5, 0.5, 0.5)


def test_border_colors_returns_tuple_for_three_component_color() -> None:
    obj = PDLayoutAttributeObject()
    # Single RGB triple -> tuple, mirroring upstream getColorOrFourColors.
    inner = COSArray()
    inner.add(COSFloat(0.25))
    inner.add(COSFloat(0.5))
    inner.add(COSFloat(0.75))
    obj.get_cos_object().set_item("BorderColor", inner)
    out = obj.get_border_colors()
    assert out == (0.25, 0.5, 0.75)


def test_border_colors_absent_returns_none() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_border_colors() is None


# ---------- /BorderStyle ----------


def test_border_style_default_none_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_border_style() == PDLayoutAttributeObject.BORDER_STYLE_NONE
    assert obj.get_border_style() == "None"


def test_border_style_single_name_round_trip_writes_cos_name() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_border_style(PDLayoutAttributeObject.BORDER_STYLE_DASHED)
    assert obj.get_border_style() == "Dashed"
    raw = obj.get_cos_object().get_dictionary_object("BorderStyle")
    assert isinstance(raw, COSName)


def test_border_style_four_array_round_trip_writes_cos_array_of_names() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_border_style(["Solid", "Dotted", "Dashed", "Double"])
    out = obj.get_border_style()
    assert out == ["Solid", "Dotted", "Dashed", "Double"]
    raw = obj.get_cos_object().get_dictionary_object("BorderStyle")
    assert isinstance(raw, COSArray)
    assert all(isinstance(raw.get_object(i), COSName) for i in range(raw.size()))


def test_border_style_set_none_removes_entry() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_border_style("Solid")
    obj.set_border_style(None)
    assert obj.get_cos_object().get_dictionary_object("BorderStyle") is None


# ---------- /BorderThickness ----------


def test_border_thickness_default_none_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    # UNSPECIFIED default -> upstream-parity returns None when missing.
    assert obj.get_border_thickness() is None


def test_border_thickness_scalar_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_border_thickness(2.5)
    assert obj.get_border_thickness() == 2.5


def test_border_thickness_four_array_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_border_thickness([1.0, 2.0, 3.0, 4.0])
    out = obj.get_border_thickness()
    assert out == [1.0, 2.0, 3.0, 4.0]
    raw = obj.get_cos_object().get_dictionary_object("BorderThickness")
    assert isinstance(raw, COSArray)


def test_border_thickness_int_writes_cos_integer() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_border_thickness(3)
    raw = obj.get_cos_object().get_dictionary_object("BorderThickness")
    assert isinstance(raw, COSInteger)


# ---------- /Padding ----------


def test_padding_default_zero_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_padding() == 0.0


def test_padding_scalar_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_padding(7.5)
    assert obj.get_padding() == 7.5


def test_padding_four_array_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_padding([1.0, 2.0, 3.0, 4.0])
    assert obj.get_padding() == [1.0, 2.0, 3.0, 4.0]


# ---------- /ColumnCount ----------


def test_column_count_default_one_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_column_count() == 1


def test_column_count_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_column_count(3)
    assert obj.get_column_count() == 3
    raw = obj.get_cos_object().get_dictionary_object("ColumnCount")
    assert isinstance(raw, COSInteger)


# ---------- /ColumnGap ----------


def test_column_gap_scalar_and_array_round_trip() -> None:
    scalar = PDLayoutAttributeObject()
    scalar.set_column_gap(12.0)
    assert scalar.get_column_gap() == 12.0

    array = PDLayoutAttributeObject()
    array.set_column_gap([6.0, 6.0, 6.0, 6.0])
    assert array.get_column_gap() == [6.0, 6.0, 6.0, 6.0]


# ---------- /ColumnWidths ----------


def test_column_widths_scalar_and_array_round_trip() -> None:
    scalar = PDLayoutAttributeObject()
    scalar.set_column_widths(72.0)
    assert scalar.get_column_widths() == 72.0

    array = PDLayoutAttributeObject()
    array.set_column_widths([72.0, 144.0, 72.0])
    assert array.get_column_widths() == [72.0, 144.0, 72.0]


# ---------- /Width ----------


def test_width_default_auto_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_width() == PDLayoutAttributeObject.WIDTH_AUTO
    assert obj.get_width() == "Auto"


def test_width_number_round_trip_and_set_auto() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_width(150.5)
    assert obj.get_width() == 150.5
    obj.set_width_auto()
    assert obj.get_width() == "Auto"
    raw = obj.get_cos_object().get_dictionary_object("Width")
    assert isinstance(raw, COSName)


# ---------- /Height ----------


def test_height_default_auto_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_height() == PDLayoutAttributeObject.HEIGHT_AUTO


def test_height_number_round_trip_and_set_auto() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_height(200)
    assert obj.get_height() == 200.0
    obj.set_height_auto()
    assert obj.get_height() == "Auto"


# ---------- /WritingMode constants exposed on the class ----------


def test_writing_mode_constants_round_trip() -> None:
    for mode in (
        PDLayoutAttributeObject.WRITING_MODE_LRTB,
        PDLayoutAttributeObject.WRITING_MODE_RLTB,
        PDLayoutAttributeObject.WRITING_MODE_TBRL,
    ):
        obj = PDLayoutAttributeObject()
        obj.set_writing_mode(mode)
        assert obj.get_writing_mode() == mode


# ---------- Dictionary-key constants (upstream-parity public statics) ----------


def test_dictionary_key_constants_match_pdf_specification() -> None:
    cls = PDLayoutAttributeObject
    assert cls.OWNER_LAYOUT == "Layout"
    assert cls.PLACEMENT == "Placement"
    assert cls.WRITING_MODE == "WritingMode"
    assert cls.BACKGROUND_COLOR == "BackgroundColor"
    assert cls.BORDER_COLOR == "BorderColor"
    assert cls.BORDER_STYLE == "BorderStyle"
    assert cls.BORDER_THICKNESS == "BorderThickness"
    assert cls.PADDING == "Padding"
    assert cls.COLOR == "Color"
    assert cls.SPACE_BEFORE == "SpaceBefore"
    assert cls.SPACE_AFTER == "SpaceAfter"
    assert cls.START_INDENT == "StartIndent"
    assert cls.END_INDENT == "EndIndent"
    assert cls.TEXT_INDENT == "TextIndent"
    assert cls.TEXT_ALIGN == "TextAlign"
    assert cls.BBOX == "BBox"
    assert cls.WIDTH == "Width"
    assert cls.HEIGHT == "Height"
    assert cls.BLOCK_ALIGN == "BlockAlign"
    assert cls.INLINE_ALIGN == "InlineAlign"
    assert cls.T_BORDER_STYLE == "TBorderStyle"
    assert cls.T_PADDING == "TPadding"
    assert cls.BASELINE_SHIFT == "BaselineShift"
    assert cls.LINE_HEIGHT == "LineHeight"
    assert cls.TEXT_DECORATION_COLOR == "TextDecorationColor"
    assert cls.TEXT_DECORATION_THICKNESS == "TextDecorationThickness"
    assert cls.TEXT_DECORATION_TYPE == "TextDecorationType"
    assert cls.RUBY_ALIGN == "RubyAlign"
    assert cls.RUBY_POSITION == "RubyPosition"
    assert cls.GLYPH_ORIENTATION_VERTICAL == "GlyphOrientationVertical"
    assert cls.COLUMN_COUNT == "ColumnCount"
    assert cls.COLUMN_GAP == "ColumnGap"
    assert cls.COLUMN_WIDTHS == "ColumnWidths"


# ---------- /TBorderStyle ----------


def test_t_border_style_default_none_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_t_border_style() == PDLayoutAttributeObject.BORDER_STYLE_NONE


def test_t_border_style_single_name_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_t_border_style(PDLayoutAttributeObject.BORDER_STYLE_DOTTED)
    assert obj.get_t_border_style() == "Dotted"
    raw = obj.get_cos_object().get_dictionary_object("TBorderStyle")
    assert isinstance(raw, COSName)


def test_t_border_style_four_array_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_t_border_styles(["Solid", "Dotted", "Dashed", "Double"])
    assert obj.get_t_border_style() == ["Solid", "Dotted", "Dashed", "Double"]


def test_t_border_style_set_all_alias() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_all_t_border_styles("Inset")
    assert obj.get_t_border_style() == "Inset"


def test_t_border_style_set_none_removes_entry() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_t_border_style("Solid")
    obj.set_t_border_styles(None)
    assert obj.get_cos_object().get_dictionary_object("TBorderStyle") is None


# ---------- /TPadding ----------


def test_t_padding_default_zero_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_t_padding() == 0.0


def test_t_padding_scalar_and_array_round_trip() -> None:
    scalar = PDLayoutAttributeObject()
    scalar.set_t_padding(4.5)
    assert scalar.get_t_padding() == 4.5

    per_side = PDLayoutAttributeObject()
    per_side.set_t_paddings([1.0, 2.0, 3.0, 4.0])
    assert per_side.get_t_padding() == [1.0, 2.0, 3.0, 4.0]


def test_t_padding_set_all_alias() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_all_t_paddings(7)
    assert obj.get_t_padding() == 7.0
    raw = obj.get_cos_object().get_dictionary_object("TPadding")
    assert isinstance(raw, COSInteger)


# ---------- /LineHeight ----------


def test_line_height_default_normal_when_absent() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_line_height() == PDLayoutAttributeObject.LINE_HEIGHT_NORMAL
    assert obj.get_line_height() == "Normal"


def test_line_height_number_round_trip_and_set_normal_auto() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_line_height(14.5)
    assert obj.get_line_height() == 14.5

    obj.set_line_height_normal()
    assert obj.get_line_height() == "Normal"
    raw_normal = obj.get_cos_object().get_dictionary_object("LineHeight")
    assert isinstance(raw_normal, COSName)

    obj.set_line_height_auto()
    assert obj.get_line_height() == "Auto"


def test_line_height_set_none_removes_entry() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_line_height(20.0)
    obj.set_line_height(None)
    assert obj.get_cos_object().get_dictionary_object("LineHeight") is None


# ---------- /TextDecorationColor / Thickness / Type ----------


def test_text_decoration_color_round_trip_and_remove() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_text_decoration_color() is None
    obj.set_text_decoration_color((0.25, 0.5, 0.75))
    assert obj.get_text_decoration_color() == pytest.approx((0.25, 0.5, 0.75))
    obj.set_text_decoration_color(None)
    assert obj.get_text_decoration_color() is None


def test_text_decoration_thickness_default_unspecified() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_text_decoration_thickness() == PDLayoutAttributeObject.UNSPECIFIED


def test_text_decoration_thickness_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_text_decoration_thickness(1.25)
    assert obj.get_text_decoration_thickness() == 1.25
    obj.set_text_decoration_thickness(2)
    raw = obj.get_cos_object().get_dictionary_object("TextDecorationThickness")
    assert isinstance(raw, COSInteger)


def test_text_decoration_type_default_none_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_text_decoration_type() == "None"
    for value in (
        PDLayoutAttributeObject.TEXT_DECORATION_TYPE_UNDERLINE,
        PDLayoutAttributeObject.TEXT_DECORATION_TYPE_OVERLINE,
        PDLayoutAttributeObject.TEXT_DECORATION_TYPE_LINE_THROUGH,
        PDLayoutAttributeObject.TEXT_DECORATION_TYPE_NONE,
    ):
        obj.set_text_decoration_type(value)
        assert obj.get_text_decoration_type() == value


# ---------- /RubyAlign ----------


def test_ruby_align_default_distribute_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_ruby_align() == PDLayoutAttributeObject.RUBY_ALIGN_DISTRIBUTE
    for value in (
        PDLayoutAttributeObject.RUBY_ALIGN_START,
        PDLayoutAttributeObject.RUBY_ALIGN_CENTER,
        PDLayoutAttributeObject.RUBY_ALIGN_END,
        PDLayoutAttributeObject.RUBY_ALIGN_JUSTIFY,
        PDLayoutAttributeObject.RUBY_ALIGN_DISTRIBUTE,
    ):
        obj.set_ruby_align(value)
        assert obj.get_ruby_align() == value


# ---------- /RubyPosition ----------


def test_ruby_position_default_before_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert obj.get_ruby_position() == PDLayoutAttributeObject.RUBY_POSITION_BEFORE
    for value in (
        PDLayoutAttributeObject.RUBY_POSITION_AFTER,
        PDLayoutAttributeObject.RUBY_POSITION_WARICHU,
        PDLayoutAttributeObject.RUBY_POSITION_INLINE,
        PDLayoutAttributeObject.RUBY_POSITION_BEFORE,
    ):
        obj.set_ruby_position(value)
        assert obj.get_ruby_position() == value


# ---------- /GlyphOrientationVertical ----------


def test_glyph_orientation_vertical_default_auto_and_round_trip() -> None:
    obj = PDLayoutAttributeObject()
    assert (
        obj.get_glyph_orientation_vertical()
        == PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_AUTO
    )
    for value in (
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_MINUS_180_DEGREES,
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_MINUS_90_DEGREES,
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_ZERO_DEGREES,
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_90_DEGREES,
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_180_DEGREES,
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_270_DEGREES,
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_360_DEGREES,
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_AUTO,
    ):
        obj.set_glyph_orientation_vertical(value)
        assert obj.get_glyph_orientation_vertical() == value


# ---------- Upstream-parity setter aliases for existing arrays ----------


def test_set_all_border_styles_and_set_border_styles() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_all_border_styles("Groove")
    assert obj.get_border_style() == "Groove"
    obj.set_border_styles(["Solid", "Dotted", "Dashed", "Double"])
    assert obj.get_border_style() == ["Solid", "Dotted", "Dashed", "Double"]
    obj.set_border_styles(None)
    assert obj.get_cos_object().get_dictionary_object("BorderStyle") is None


def test_set_all_border_thicknesses_and_set_border_thicknesses() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_all_border_thicknesses(2)
    assert obj.get_border_thickness() == 2.0
    obj.set_border_thicknesses([1.0, 2.0, 3.0, 4.0])
    assert obj.get_border_thickness() == [1.0, 2.0, 3.0, 4.0]
    obj.set_border_thicknesses(None)
    assert obj.get_cos_object().get_dictionary_object("BorderThickness") is None


def test_set_all_paddings_and_set_paddings() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_all_paddings(5.0)
    assert obj.get_padding() == 5.0
    obj.set_paddings([1.0, 2.0, 3.0, 4.0])
    assert obj.get_padding() == [1.0, 2.0, 3.0, 4.0]
    obj.set_paddings(None)
    assert obj.get_cos_object().get_dictionary_object("Padding") is None


def test_set_all_column_widths_and_set_column_gaps() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_all_column_widths(72.0)
    assert obj.get_column_widths() == 72.0
    obj.set_column_gaps([6.0, 6.0])
    assert obj.get_column_gap() == [6.0, 6.0]
    obj.set_column_gaps(None)
    assert obj.get_cos_object().get_dictionary_object("ColumnGap") is None


# ---------- /BorderColor — set_all_border_colors (single-RGB) ----------


def test_set_all_border_colors_writes_three_component_array() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_all_border_colors((0.1, 0.2, 0.3))
    # Polymorphic getter returns a tuple for 3-component, PDFourColours for 4.
    assert obj.get_border_colors() == pytest.approx((0.1, 0.2, 0.3))
    raw = obj.get_cos_object().get_dictionary_object("BorderColor")
    assert isinstance(raw, COSArray)
    assert raw.size() == 3


def test_set_all_border_colors_none_removes_entry() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_all_border_colors((0.5, 0.5, 0.5))
    obj.set_all_border_colors(None)
    assert obj.get_cos_object().get_dictionary_object("BorderColor") is None
    assert obj.get_border_colors() is None


def test_set_all_border_colors_overwrites_four_colours() -> None:
    obj = PDLayoutAttributeObject()
    four = PDFourColours()
    four.set_top((1.0, 0.0, 0.0))
    four.set_right((0.0, 1.0, 0.0))
    four.set_bottom((0.0, 0.0, 1.0))
    four.set_left((0.5, 0.5, 0.5))
    obj.set_border_colors(four)
    obj.set_all_border_colors((0.7, 0.7, 0.7))
    raw = obj.get_cos_object().get_dictionary_object("BorderColor")
    assert isinstance(raw, COSArray)
    assert raw.size() == 3
    assert obj.get_border_colors() == pytest.approx((0.7, 0.7, 0.7))


# ---------- __str__ (toString parity) ----------


def test_str_owner_only_when_no_attributes_specified() -> None:
    obj = PDLayoutAttributeObject()
    assert str(obj) == "O=Layout"


def test_str_appends_scalar_attributes_in_upstream_order() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_placement(PDLayoutAttributeObject.PLACEMENT_BLOCK)
    obj.set_writing_mode(PDLayoutAttributeObject.WRITING_MODE_RLTB)
    obj.set_space_before(5.0)
    out = str(obj)
    # Owner first, then specified entries in upstream key order.
    assert out.startswith("O=Layout")
    placement_idx = out.index("Placement=Block")
    writing_idx = out.index("WritingMode=RlTb")
    space_idx = out.index("SpaceBefore=5.0")
    assert placement_idx < writing_idx < space_idx


def test_str_skips_unspecified_default_returns() -> None:
    # get_placement() returns "Inline" by default but the entry isn't set,
    # so toString must not include it.
    obj = PDLayoutAttributeObject()
    assert obj.get_placement() == "Inline"
    assert "Placement=" not in str(obj)


def test_str_formats_array_values_with_brackets() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_padding([1.0, 2.0, 3.0, 4.0])
    obj.set_border_style(["Solid", "Dotted", "Dashed", "Double"])
    out = str(obj)
    assert "Padding=[1.0, 2.0, 3.0, 4.0]" in out
    assert "BorderStyle=[Solid, Dotted, Dashed, Double]" in out


def test_str_formats_scalar_polymorphic_values_inline() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_padding(7.5)
    obj.set_border_style(PDLayoutAttributeObject.BORDER_STYLE_SOLID)
    out = str(obj)
    assert "Padding=7.5" in out
    assert "BorderStyle=Solid" in out


def test_str_includes_column_and_decoration_fields() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_column_count(3)
    obj.set_column_gap([6.0, 6.0])
    obj.set_text_decoration_type(
        PDLayoutAttributeObject.TEXT_DECORATION_TYPE_UNDERLINE
    )
    obj.set_glyph_orientation_vertical(
        PDLayoutAttributeObject.GLYPH_ORIENTATION_VERTICAL_90_DEGREES
    )
    out = str(obj)
    assert "ColumnCount=3" in out
    assert "ColumnGap=[6.0, 6.0]" in out
    assert "TextDecorationType=Underline" in out
    assert "GlyphOrientationVertical=90" in out
