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
