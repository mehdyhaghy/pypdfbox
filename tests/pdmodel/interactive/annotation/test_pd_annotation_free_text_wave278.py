from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_DA = COSName.get_pdf_name("DA")
_DS = COSName.get_pdf_name("DS")
_RC = COSName.get_pdf_name("RC")
_Q = COSName.get_pdf_name("Q")
_IT = COSName.get_pdf_name("IT")
_CL = COSName.get_pdf_name("CL")
_LE = COSName.get_pdf_name("LE")
_RD = COSName.get_pdf_name("RD")
_BS = COSName.get_pdf_name("BS")
_BE = COSName.get_pdf_name("BE")


def _float_array(*values: float) -> COSArray:
    return COSArray([COSFloat(value) for value in values])


def test_default_appearance_style_and_rich_contents_clear_to_absent() -> None:
    ann = PDAnnotationFreeText()

    ann.set_default_appearance("/Helv 9 Tf 0 g")
    ann.set_default_style_string("font: 9pt Helvetica; color: #000000")
    ann.set_rich_contents("<body><p>hello</p></body>")

    assert ann.get_default_appearance() == "/Helv 9 Tf 0 g"
    assert ann.get_default_style_string() == "font: 9pt Helvetica; color: #000000"
    assert ann.get_rich_contents() == "<body><p>hello</p></body>"

    ann.set_default_appearance(None)
    ann.set_default_style_string(None)
    ann.set_rich_contents(None)

    cos = ann.get_cos_object()
    assert ann.get_default_appearance() is None
    assert ann.get_default_style_string() is None
    assert ann.get_rich_contents() is None
    assert not cos.contains_key(_DA)
    assert not cos.contains_key(_DS)
    assert not cos.contains_key(_RC)


def test_quadding_reads_defaults_and_existing_numeric_cos_values() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_q() == PDAnnotationFreeText.QUADDING_LEFT

    ann.set_q(PDAnnotationFreeText.QUADDING_CENTERED)
    assert ann.get_q() == PDAnnotationFreeText.Q_CENTERED

    ann.get_cos_object().set_item(_Q, COSFloat(2.9))
    assert ann.get_q() == PDAnnotationFreeText.Q_RIGHT_JUSTIFIED


def test_callout_line_reads_four_or_six_coordinates_and_round_trips_cos() -> None:
    ann = PDAnnotationFreeText()

    ann.set_callout_line([1, 2, 3, 4])
    assert ann.get_callout_line() == [1.0, 2.0, 3.0, 4.0]
    callout = ann.get_cos_object().get_dictionary_object(_CL)
    assert isinstance(callout, COSArray)
    assert callout.to_float_array() == [1.0, 2.0, 3.0, 4.0]

    ann.get_cos_object().set_item(_CL, _float_array(10, 20, 30, 40, 50, 60, 70))
    assert ann.get_callout_line() == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    assert ann.get_callout() == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]


def test_callout_alias_matches_pdfbox_raw_float_array_conversion() -> None:
    ann = PDAnnotationFreeText()
    ann.get_cos_object().set_item(
        _CL,
        COSArray(
            [
                COSFloat(1),
                COSName.get_pdf_name("Bad"),
                COSFloat(3),
                COSFloat(4),
                COSFloat(5),
                COSFloat(6),
                COSFloat(7),
            ]
        ),
    )

    assert ann.get_callout_line() is None
    assert ann.get_callout() == [1.0, 0.0, 3.0, 4.0, 5.0, 6.0, 7.0]


def test_rectangle_differences_plural_singular_and_clear_paths_share_rd() -> None:
    ann = PDAnnotationFreeText()

    ann.set_rect_differences(2.5)
    assert ann.get_rectangle_differences() == [2.5, 2.5, 2.5, 2.5]
    assert ann.get_rect_differences() == [2.5, 2.5, 2.5, 2.5]

    ann.set_rectangle_differences([1, 2, 3, 4])
    rect = ann.get_rect_difference()
    assert rect is not None
    assert rect.get_lower_left_x() == 1.0
    assert rect.get_lower_left_y() == 2.0
    assert rect.get_upper_right_x() == 3.0
    assert rect.get_upper_right_y() == 4.0

    ann.set_rect_difference(PDRectangle(5, 6, 7, 8))
    assert ann.get_rectangle_differences() == [5.0, 6.0, 7.0, 8.0]

    ann.set_rect_differences(None)
    assert ann.get_rectangle_differences() is None
    assert ann.get_rect_differences() == []
    assert not ann.get_cos_object().contains_key(_RD)


def test_border_effect_and_border_style_wrappers_preserve_underlying_cos() -> None:
    ann = PDAnnotationFreeText()
    bs = PDBorderStyleDictionary()
    bs.set_width(3)
    bs.set_style(PDBorderStyleDictionary.STYLE_UNDERLINE)
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(1.25)

    ann.set_border_style(bs)
    ann.set_border_effect(be)

    assert ann.get_cos_object().get_dictionary_object(_BS) is bs.get_cos_object()
    assert ann.get_cos_object().get_dictionary_object(_BE) is be.get_cos_object()
    border_style = ann.get_border_style()
    border_effect = ann.get_border_effect()
    assert border_style is not None
    assert border_effect is not None
    assert border_style.get_style() == PDBorderStyleDictionary.STYLE_UNDERLINE
    assert border_effect.get_style() == PDBorderEffectDictionary.STYLE_CLOUDY
    assert border_effect.get_intensity() == 1.25

    ann.set_border_style(None)
    ann.set_border_effect(None)
    assert ann.get_border_style() is None
    assert ann.get_border_effect() is None


def test_line_ending_style_default_round_trip_and_clear() -> None:
    ann = PDAnnotationFreeText()

    assert ann.get_line_ending_style() == PDAnnotationLine.LE_NONE

    ann.set_line_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    assert ann.get_line_ending() == PDAnnotationLine.LE_OPEN_ARROW
    assert ann.get_cos_object().get_name(_LE) == PDAnnotationLine.LE_OPEN_ARROW

    ann.set_line_ending_style(None)
    assert ann.get_line_ending_style() == PDAnnotationLine.LE_NONE
    assert not ann.get_cos_object().contains_key(_LE)


def test_existing_cos_dictionary_round_trips_free_text_entries() -> None:
    cos = COSDictionary()
    cos.set_string(_DA, "/F1 11 Tf 0 0 1 rg")
    cos.set_string(_DS, "font: 11pt serif")
    cos.set_string(_RC, "<p>rich</p>")
    cos.set_int(_Q, PDAnnotationFreeText.Q_RIGHT_JUSTIFIED)
    cos.set_name(_IT, PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    cos.set_item(_CL, _float_array(1, 2, 3, 4, 5, 6))
    cos.set_name(_LE, PDAnnotationLine.LE_CLOSED_ARROW)
    cos.set_item(_RD, _float_array(0.5, 1.5, 2.5, 3.5))

    ann = PDAnnotationFreeText(cos)

    assert ann.get_cos_object() is cos
    assert ann.get_default_appearance() == "/F1 11 Tf 0 0 1 rg"
    assert ann.get_default_style_string() == "font: 11pt serif"
    assert ann.get_rich_contents() == "<p>rich</p>"
    assert ann.get_q() == PDAnnotationFreeText.Q_RIGHT_JUSTIFIED
    assert ann.is_free_text_callout() is True
    assert ann.get_callout_line() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert ann.get_line_ending_style() == PDAnnotationLine.LE_CLOSED_ARROW
    assert ann.get_rect_differences() == [0.5, 1.5, 2.5, 3.5]


def test_malformed_callout_shapes_return_none() -> None:
    ann = PDAnnotationFreeText()

    ann.get_cos_object().set_item(_CL, COSString("not an array"))
    assert ann.get_callout_line() is None

    ann.get_cos_object().set_item(_CL, _float_array(1, 2, 3))
    assert ann.get_callout_line() is None

    ann.get_cos_object().set_item(
        _CL,
        COSArray(
            [
                COSFloat(1),
                COSName.get_pdf_name("Bad"),
                COSFloat(3),
                COSFloat(4),
            ]
        ),
    )
    assert ann.get_callout_line() is None


def test_malformed_rectangle_differences_return_none_without_coercion() -> None:
    ann = PDAnnotationFreeText()

    # Non-array /RD: every accessor returns None / [] (Java returns null too).
    ann.get_cos_object().set_item(_RD, COSString("not an array"))
    assert ann.get_rectangle_differences() is None
    assert ann.get_rect_difference() is None

    # Wave 1515: oracle-validated. get_rectangle_differences /
    # get_rect_differences are pypdfbox-specific STRICT accessors that keep
    # returning None / [] for a short or non-numeric /RD. But the
    # upstream-named get_rect_difference() mirrors PDFBox 3.0.7's tolerant
    # PDRectangle(COSArray) wrap: a short [1 2 3] pads to [1 2 3 0] then
    # normalizes -> (1,0,3,2); a non-numeric member becomes 0.0.
    ann.get_cos_object().set_item(_RD, _float_array(1, 2, 3))
    assert ann.get_rectangle_differences() is None
    rd3 = ann.get_rect_difference()
    assert rd3 is not None
    assert (
        rd3.get_lower_left_x(),
        rd3.get_lower_left_y(),
        rd3.get_upper_right_x(),
        rd3.get_upper_right_y(),
    ) == (1.0, 0.0, 3.0, 2.0)

    ann.get_cos_object().set_item(
        _RD,
        COSArray(
            [
                COSFloat(1),
                COSName.get_pdf_name("Bad"),
                COSFloat(3),
                COSFloat(4),
            ]
        ),
    )
    assert ann.get_rectangle_differences() is None
    assert ann.get_rect_differences() == []
    # Non-numeric member -> 0.0, so [1 0 3 4] normalizes to (1,0,3,4).
    rd_bad = ann.get_rect_difference()
    assert rd_bad is not None
    assert (
        rd_bad.get_lower_left_x(),
        rd_bad.get_lower_left_y(),
        rd_bad.get_upper_right_x(),
        rd_bad.get_upper_right_y(),
    ) == (1.0, 0.0, 3.0, 4.0)
