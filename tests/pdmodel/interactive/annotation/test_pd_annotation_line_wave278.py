"""Wave 278 coverage for ``PDAnnotationLine`` convenience edges."""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)

_BS = COSName.get_pdf_name("BS")
_CAP = COSName.get_pdf_name("Cap")
_CO = COSName.get_pdf_name("CO")
_CP = COSName.get_pdf_name("CP")
_IC = COSName.get_pdf_name("IC")
_L = COSName.get_pdf_name("L")
_LE = COSName.get_pdf_name("LE")
_LL = COSName.get_pdf_name("LL")
_LLE = COSName.get_pdf_name("LLE")
_LLO = COSName.get_pdf_name("LLO")
_SUBTYPE = COSName.get_pdf_name("Subtype")


def _float_array(values: list[float]) -> COSArray:
    return COSArray([COSFloat(value) for value in values])


# ---------- /L line coordinates ----------


def test_line_coordinates_setter_writes_four_float_entries_wave278() -> None:
    ann = PDAnnotationLine()

    ann.set_line([10, -2.5, 30.25, 40])

    assert ann.get_line() == [10.0, -2.5, 30.25, 40.0]
    raw = ann.get_cos_object().get_dictionary_object(_L)
    assert isinstance(raw, COSArray)
    assert raw.size() == 4
    assert raw.to_float_array() == [10.0, -2.5, 30.25, 40.0]


def test_line_coordinates_raw_long_array_is_truncated_wave278() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(_L, _float_array([1.0, 2.0, 3.0, 4.0, 999.0]))

    assert PDAnnotationLine(dictionary).get_line() == [1.0, 2.0, 3.0, 4.0]


def test_line_coordinates_malformed_shapes_return_none_wave278() -> None:
    dictionary = COSDictionary()
    ann = PDAnnotationLine(dictionary)

    dictionary.set_item(_L, COSName.get_pdf_name("NotAnArray"))
    assert ann.get_line() is None

    dictionary.set_item(_L, _float_array([1.0, 2.0, 3.0]))
    assert ann.get_line() is None


# ---------- /LE line endings ----------


def test_line_ending_defaults_and_padding_wave278() -> None:
    ann = PDAnnotationLine()
    raw = COSArray([COSName.get_pdf_name(PDAnnotationLine.LE_OPEN_ARROW)])
    ann.get_cos_object().set_item(_LE, raw)

    assert ann.get_start_point_ending_style() == PDAnnotationLine.LE_OPEN_ARROW
    assert ann.get_end_point_ending_style() == PDAnnotationLine.LE_NONE

    ann.set_end_point_ending_style(PDAnnotationLine.LE_CLOSED_ARROW)
    assert raw.size() == 2
    assert ann.get_end_point_ending_style() == PDAnnotationLine.LE_CLOSED_ARROW


def test_line_ending_malformed_shapes_fall_back_to_none_wave278() -> None:
    dictionary = COSDictionary()
    ann = PDAnnotationLine(dictionary)

    dictionary.set_item(_LE, COSString("bad"))
    assert ann.get_start_point_ending_style() == PDAnnotationLine.LE_NONE
    assert ann.get_end_point_ending_style() == PDAnnotationLine.LE_NONE

    dictionary.set_item(_LE, COSArray([COSString("bad"), COSInteger.get(7)]))
    assert ann.get_start_point_ending_style() == PDAnnotationLine.LE_NONE
    assert ann.get_end_point_ending_style() == PDAnnotationLine.LE_NONE


# ---------- /Cap, /CO, /CP captions ----------


def test_caption_flag_offsets_and_position_round_trip_wave278() -> None:
    ann = PDAnnotationLine()

    assert ann.get_caption() is False
    assert ann.has_caption() is False
    assert ann.get_caption_horizontal_offset() == 0.0
    assert ann.get_caption_vertical_offset() == 0.0
    assert ann.get_caption_positioning() is None

    ann.set_caption(True)
    ann.set_caption_horizontal_offset(2.25)
    ann.set_caption_vertical_offset(-3.5)
    ann.set_caption_positioning("Top")

    assert ann.get_caption() is True
    assert ann.has_caption() is True
    assert ann.get_caption_horizontal_offset() == 2.25
    assert ann.get_caption_vertical_offset() == -3.5
    assert ann.get_caption_positioning() == "Top"

    ann.set_caption(False)
    ann.set_caption_positioning(None)
    assert ann.get_caption() is False
    assert not ann.get_cos_object().contains_key(_CP)


def test_caption_offset_setters_pad_existing_short_array_wave278() -> None:
    ann = PDAnnotationLine()
    raw = COSArray([COSFloat(1.5)])
    ann.get_cos_object().set_item(_CO, raw)

    ann.set_caption_vertical_offset(8.0)

    assert raw.size() == 2
    assert ann.get_caption_horizontal_offset() == 1.5
    assert ann.get_caption_vertical_offset() == 8.0


def test_caption_malformed_shapes_use_defaults_wave278() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(_CAP, COSString("true"))
    dictionary.set_item(_CO, COSString("bad"))
    dictionary.set_item(_CP, COSString("bad"))
    ann = PDAnnotationLine(dictionary)

    assert ann.get_caption() is False
    assert ann.get_caption_horizontal_offset() == 0.0
    assert ann.get_caption_vertical_offset() == 0.0
    assert ann.get_caption_positioning() is None

    dictionary.set_item(_CO, COSArray([COSString("bad"), COSString("bad")]))
    assert ann.get_caption_horizontal_offset() == 0.0
    assert ann.get_caption_vertical_offset() == 0.0


# ---------- leader lines ----------


def test_leader_line_lengths_default_set_and_raw_round_trip_wave278() -> None:
    ann = PDAnnotationLine()

    assert ann.get_leader_line_length() == 0.0
    assert ann.get_leader_line_extension_length() == 0.0
    assert ann.get_leader_line_offset_length() == 0.0

    ann.set_leader_line_length(12.5)
    ann.set_leader_line_extension_length(3.25)
    ann.set_leader_line_offset_length(-1.0)

    assert ann.get_leader_line_length() == 12.5
    assert ann.get_leader_line_extension_length() == 3.25
    assert ann.get_leader_line_offset_length() == -1.0
    assert ann.get_cos_object().get_float(_LL) == 12.5
    assert ann.get_cos_object().get_float(_LLE) == 3.25
    assert ann.get_cos_object().get_float(_LLO) == -1.0


def test_leader_line_malformed_shapes_use_defaults_wave278() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(_LL, COSString("bad"))
    dictionary.set_item(_LLE, COSName.get_pdf_name("bad"))
    dictionary.set_item(_LLO, COSArray())
    ann = PDAnnotationLine(dictionary)

    assert ann.get_leader_line_length() == 0.0
    assert ann.get_leader_line_extension_length() == 0.0
    assert ann.get_leader_line_offset_length() == 0.0


# ---------- /IC interior color ----------


@pytest.mark.parametrize(
    "components",
    ([0.25], [0.25, 0.5, 0.75], [0.1, 0.2, 0.3, 0.4]),
)
def test_interior_color_component_arrays_round_trip_wave278(
    components: list[float],
) -> None:
    ann = PDAnnotationLine()

    ann.set_interior_color(components)

    assert ann.get_interior_color() == pytest.approx(components)
    raw = ann.get_cos_object().get_dictionary_object(_IC)
    assert isinstance(raw, COSArray)
    assert raw.to_float_array() == pytest.approx(components)


def test_interior_color_tuple_and_clear_wave278() -> None:
    ann = PDAnnotationLine()

    ann.set_interior_color((1.0, 0.0, 0.5))
    assert ann.get_interior_color() == [1.0, 0.0, 0.5]

    ann.set_interior_color(None)
    assert ann.get_interior_color() is None
    assert not ann.get_cos_object().contains_key(_IC)


def test_interior_color_malformed_shape_returns_none_wave278() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(_IC, COSName.get_pdf_name("Bad"))

    assert PDAnnotationLine(dictionary).get_interior_color() is None


# ---------- inherited /BS border style ----------


def test_border_style_inherited_from_markup_round_trip_wave278() -> None:
    ann = PDAnnotationLine()
    bs = PDBorderStyleDictionary()
    bs.set_width(2.5)
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    bs.set_dash_style([3.0, 1.0])

    ann.set_border_style(bs)

    resolved = ann.get_border_style()
    assert resolved is not None
    assert resolved.get_cos_object() is bs.get_cos_object()
    assert resolved.get_width() == 2.5
    assert resolved.get_style() == PDBorderStyleDictionary.STYLE_DASHED
    dash = resolved.get_dash_style()
    assert dash is not None
    assert dash.get_dash_array() == [3.0, 1.0]


def test_border_style_clear_default_and_malformed_shape_wave278() -> None:
    ann = PDAnnotationLine()
    assert ann.get_border_style() is None

    ann.set_border_style(PDBorderStyleDictionary())
    ann.set_border_style(None)
    assert ann.get_border_style() is None
    assert not ann.get_cos_object().contains_key(_BS)

    ann.get_cos_object().set_item(_BS, COSString("bad"))
    assert ann.get_border_style() is None


# ---------- COS round-trip ----------


def test_line_annotation_create_round_trip_preserves_cos_dictionary_wave278() -> None:
    dictionary = COSDictionary()
    dictionary.set_name(_SUBTYPE, PDAnnotationLine.SUB_TYPE)
    dictionary.set_item(_L, _float_array([1.0, 2.0, 3.0, 4.0]))
    dictionary.set_item(
        _LE,
        COSArray(
            [
                COSName.get_pdf_name(PDAnnotationLine.LE_CIRCLE),
                COSName.get_pdf_name(PDAnnotationLine.LE_SLASH),
            ]
        ),
    )
    dictionary.set_boolean(_CAP, True)
    dictionary.set_item(_CO, _float_array([5.0, 6.0]))
    dictionary.set_float(_LL, 7.0)
    dictionary.set_float(_LLE, 8.0)
    dictionary.set_float(_LLO, 9.0)
    dictionary.set_item(_IC, _float_array([0.2, 0.4, 0.6]))

    ann = PDAnnotation.create(dictionary)

    assert isinstance(ann, PDAnnotationLine)
    assert ann.get_cos_object() is dictionary
    assert ann.get_line() == [1.0, 2.0, 3.0, 4.0]
    assert ann.get_start_point_ending_style() == PDAnnotationLine.LE_CIRCLE
    assert ann.get_end_point_ending_style() == PDAnnotationLine.LE_SLASH
    assert ann.get_caption() is True
    assert ann.get_caption_horizontal_offset() == 5.0
    assert ann.get_caption_vertical_offset() == 6.0
    assert ann.get_leader_line_length() == 7.0
    assert ann.get_leader_line_extension_length() == 8.0
    assert ann.get_leader_line_offset_length() == 9.0
    assert ann.get_interior_color() == pytest.approx([0.2, 0.4, 0.6])

    ann.set_line([10.0, 11.0, 12.0, 13.0])
    raw_line = dictionary.get_dictionary_object(_L)
    assert isinstance(raw_line, COSArray)
    assert raw_line.to_float_array() == [10.0, 11.0, 12.0, 13.0]
