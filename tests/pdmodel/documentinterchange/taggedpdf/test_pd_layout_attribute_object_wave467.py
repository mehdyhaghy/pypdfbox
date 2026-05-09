from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDFourColours,
    PDLayoutAttributeObject,
)


def test_wave467_set_color_supports_named_and_default_color_slots() -> None:
    obj = PDLayoutAttributeObject()

    obj.set_color((0.1, 0.2, 0.3))
    obj.set_color("TextDecorationColor", (0.4, 0.5, 0.6))

    assert obj.get_color() == pytest.approx((0.1, 0.2, 0.3))
    assert obj.get_color("TextDecorationColor") == pytest.approx((0.4, 0.5, 0.6))

    obj.set_color("TextDecorationColor", None)
    assert obj.get_color("TextDecorationColor") is None


def test_wave467_set_t_border_style_list_and_none_branches() -> None:
    obj = PDLayoutAttributeObject()

    obj.set_t_border_style(["Solid", "Dotted", "Dashed", "Double"])

    assert obj.get_t_border_style() == ["Solid", "Dotted", "Dashed", "Double"]
    assert isinstance(obj.get_cos_object().get_dictionary_object("TBorderStyle"), COSArray)

    obj.set_t_border_style(None)
    assert obj.get_cos_object().get_dictionary_object("TBorderStyle") is None


def test_wave467_str_includes_all_remaining_layout_fields() -> None:
    obj = PDLayoutAttributeObject()
    four = PDFourColours.single_color((0.0, 0.0, 0.0))

    obj.set_background_color((0.1, 0.2, 0.3))
    obj.set_border_colors(four)
    obj.set_border_thicknesses([1.0, 2.0, 3.0, 4.0])
    obj.set_color((0.4, 0.5, 0.6))
    obj.set_space_after(2)
    obj.set_start_indent(3)
    obj.set_end_indent(4)
    obj.set_text_indent(5)
    obj.set_text_align(PDLayoutAttributeObject.TEXT_ALIGN_CENTER)
    obj.set_b_box((0.0, 1.0, 2.0, 3.0))
    obj.set_width(72)
    obj.set_height(144)
    obj.set_block_align(PDLayoutAttributeObject.BLOCK_ALIGN_AFTER)
    obj.set_inline_align(PDLayoutAttributeObject.INLINE_ALIGN_END)
    obj.set_t_border_styles(["Inset", "Outset", "Ridge", "Groove"])
    obj.set_t_paddings([5.0, 6.0, 7.0, 8.0])
    obj.set_baseline_shift(9)
    obj.set_line_height(PDLayoutAttributeObject.LINE_HEIGHT_AUTO)
    obj.set_text_decoration_color((0.7, 0.8, 0.9))
    obj.set_text_decoration_thickness(1)
    obj.set_ruby_align(PDLayoutAttributeObject.RUBY_ALIGN_CENTER)
    obj.set_ruby_position(PDLayoutAttributeObject.RUBY_POSITION_AFTER)
    obj.set_column_widths([20.0, 30.0])

    text = str(obj)

    assert "BackgroundColor=(0.10000000149011612, 0.20000000298023224" in text
    assert "BorderColor=" in text
    assert "BorderThickness=[1.0, 2.0, 3.0, 4.0]" in text
    assert "Color=(0.4000000059604645, 0.5, 0.6000000238418579)" in text
    assert "SpaceAfter=2.0" in text
    assert "StartIndent=3.0" in text
    assert "EndIndent=4.0" in text
    assert "TextIndent=5.0" in text
    assert "TextAlign=Center" in text
    assert "BBox=(0.0, 1.0, 2.0, 3.0)" in text
    assert "Width=72.0" in text
    assert "Height=144.0" in text
    assert "BlockAlign=After" in text
    assert "InlineAlign=End" in text
    assert "TBorderStyle=[Inset, Outset, Ridge, Groove]" in text
    assert "TPadding=[5.0, 6.0, 7.0, 8.0]" in text
    assert "BaselineShift=9.0" in text
    assert "LineHeight=Auto" in text
    assert "TextDecorationColor=(0.699999988079071, 0.800000011920929" in text
    assert "TextDecorationThickness=1.0" in text
    assert "RubyAlign=Center" in text
    assert "RubyPosition=After" in text
    assert "ColumnWidths=[20.0, 30.0]" in text
