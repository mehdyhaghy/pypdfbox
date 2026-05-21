"""Upstream-parity port for ``PDAnnotationLine``.

Mirrors ``PDAnnotationLine.java`` (PDFBox 3.0.x). Upstream ships no
JUnit test for the line-annotation wrapper — this module ports the
source's behavioural contract: SUB_TYPE stamp, /L coordinate accessor,
/LE end-style pair (default ``None``), /IT intent, /Cap caption flag,
/CO caption-offset pair, /LL /LLE /LLO leader-line lengths, /CP caption
positioning, and /IC interior-color array.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import PDAnnotationLine

_L = COSName.get_pdf_name("L")
_LE = COSName.get_pdf_name("LE")


def test_default_constructor_stamps_subtype_and_seeds_l():
    # Upstream constructor stamps /Subtype /Line and seeds /L with
    # [0, 0, 0, 0] (the spec marks /L as mandatory).
    ann = PDAnnotationLine()
    assert ann.get_subtype() == "Line"
    assert ann.get_line() == [0.0, 0.0, 0.0, 0.0]


def test_set_and_get_line_round_trip():
    ann = PDAnnotationLine()
    ann.set_line([10.0, 20.0, 30.0, 40.0])
    assert ann.get_line() == [10.0, 20.0, 30.0, 40.0]


def test_get_line_returns_none_when_unset():
    # Wrap a dict with no /L entry — upstream returns null.
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Subtype"), "Line")
    ann = PDAnnotationLine(d)
    assert ann.get_line() is None


def test_start_and_end_point_ending_style_default_none():
    # Upstream returns LE_NONE when /LE is missing.
    ann = PDAnnotationLine()
    assert ann.get_start_point_ending_style() == "None"
    assert ann.get_end_point_ending_style() == "None"


def test_set_start_point_ending_style_seeds_le_array():
    ann = PDAnnotationLine()
    ann.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    assert ann.get_start_point_ending_style() == "OpenArrow"
    assert ann.get_end_point_ending_style() == "None"
    arr = ann.get_cos_object().get_dictionary_object(_LE)
    assert isinstance(arr, COSArray)
    assert arr.size() == 2


def test_set_end_point_ending_style_seeds_le_array():
    ann = PDAnnotationLine()
    ann.set_end_point_ending_style(PDAnnotationLine.LE_DIAMOND)
    assert ann.get_start_point_ending_style() == "None"
    assert ann.get_end_point_ending_style() == "Diamond"


def test_set_start_and_end_styles_independently_after_seeding():
    ann = PDAnnotationLine()
    ann.set_start_point_ending_style(PDAnnotationLine.LE_SQUARE)
    ann.set_end_point_ending_style(PDAnnotationLine.LE_CIRCLE)
    assert ann.get_start_point_ending_style() == "Square"
    assert ann.get_end_point_ending_style() == "Circle"


def test_set_start_point_ending_style_none_coerces_to_le_none():
    # Upstream: ``style == null ? LE_NONE : style``.
    ann = PDAnnotationLine()
    ann.set_start_point_ending_style(PDAnnotationLine.LE_SQUARE)
    ann.set_start_point_ending_style(None)
    assert ann.get_start_point_ending_style() == "None"


def test_caption_default_false_and_round_trip():
    ann = PDAnnotationLine()
    assert ann.has_caption() is False
    ann.set_caption(True)
    assert ann.has_caption() is True
    ann.set_caption(False)
    assert ann.has_caption() is False


def test_caption_horizontal_offset_default_zero():
    ann = PDAnnotationLine()
    assert ann.get_caption_horizontal_offset() == 0.0
    ann.set_caption_horizontal_offset(12.5)
    assert ann.get_caption_horizontal_offset() == 12.5
    # /CO is a 2-element array — y offset stays 0 after only x being set.
    assert ann.get_caption_vertical_offset() == 0.0


def test_caption_vertical_offset_default_zero():
    ann = PDAnnotationLine()
    assert ann.get_caption_vertical_offset() == 0.0
    ann.set_caption_vertical_offset(-3.0)
    assert ann.get_caption_vertical_offset() == -3.0
    assert ann.get_caption_horizontal_offset() == 0.0


def test_leader_line_length_default_zero_round_trip():
    ann = PDAnnotationLine()
    assert ann.get_leader_line_length() == 0.0
    ann.set_leader_line_length(15.0)
    assert ann.get_leader_line_length() == 15.0


def test_leader_line_extension_length_default_zero_round_trip():
    ann = PDAnnotationLine()
    assert ann.get_leader_line_extension_length() == 0.0
    ann.set_leader_line_extension_length(4.0)
    assert ann.get_leader_line_extension_length() == 4.0


def test_leader_line_offset_length_default_zero_round_trip():
    ann = PDAnnotationLine()
    assert ann.get_leader_line_offset_length() == 0.0
    ann.set_leader_line_offset_length(7.5)
    assert ann.get_leader_line_offset_length() == 7.5


def test_caption_positioning_get_set_round_trip():
    ann = PDAnnotationLine()
    assert ann.get_caption_positioning() is None
    ann.set_caption_positioning("Top")
    assert ann.get_caption_positioning() == "Top"
    ann.set_caption_positioning("Inline")
    assert ann.get_caption_positioning() == "Inline"


def test_interior_color_set_and_get_rgb():
    ann = PDAnnotationLine()
    assert ann.get_interior_color() is None
    ann.set_interior_color([0.25, 0.5, 0.75])
    assert ann.get_interior_color() == [0.25, 0.5, 0.75]


def test_le_constants_match_spec():
    # PDF 32000-1 Table 176 line-ending styles.
    assert PDAnnotationLine.LE_NONE == "None"
    assert PDAnnotationLine.LE_SQUARE == "Square"
    assert PDAnnotationLine.LE_CIRCLE == "Circle"
    assert PDAnnotationLine.LE_DIAMOND == "Diamond"
    assert PDAnnotationLine.LE_OPEN_ARROW == "OpenArrow"
    assert PDAnnotationLine.LE_CLOSED_ARROW == "ClosedArrow"
    assert PDAnnotationLine.LE_BUTT == "Butt"
    assert PDAnnotationLine.LE_R_OPEN_ARROW == "ROpenArrow"
    assert PDAnnotationLine.LE_R_CLOSED_ARROW == "RClosedArrow"
    assert PDAnnotationLine.LE_SLASH == "Slash"


def test_it_constants_match_spec():
    assert PDAnnotationLine.IT_LINE_ARROW == "LineArrow"
    assert PDAnnotationLine.IT_LINE_DIMENSION == "LineDimension"


def test_sub_type_constant_equals_line():
    assert PDAnnotationLine.SUB_TYPE == "Line"
