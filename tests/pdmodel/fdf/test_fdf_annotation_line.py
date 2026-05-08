from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFAnnotationLine


def test_default_constructor_stamps_subtype_line() -> None:
    a = FDFAnnotationLine()
    assert a.get_subtype() == "Line"


def test_start_and_end_points_round_trip() -> None:
    a = FDFAnnotationLine()
    assert a.get_start_point() is None
    assert a.get_end_point() is None
    a.set_start_point(10.0, 20.0)
    a.set_end_point(30.0, 40.0)
    assert a.get_start_point() == (10.0, 20.0)
    assert a.get_end_point() == (30.0, 40.0)


def test_line_round_trip_and_point_helpers() -> None:
    a = FDFAnnotationLine()
    assert a.get_line() is None

    a.set_line([10.0, -2.5, 30.25, 40.0])

    assert a.get_line() == [10.0, -2.5, 30.25, 40.0]
    assert a.get_start_point() == (10.0, -2.5)
    assert a.get_end_point() == (30.25, 40.0)
    raw = a.get_cos_object().get_dictionary_object(COSName.get_pdf_name("L"))
    assert isinstance(raw, COSArray)
    assert raw.to_float_array() == [10.0, -2.5, 30.25, 40.0]


def test_line_rejects_wrong_length() -> None:
    a = FDFAnnotationLine()

    with pytest.raises(ValueError, match="4-element"):
        a.set_line([1.0, 2.0, 3.0])


def test_line_raw_long_array_is_truncated_to_first_four_values() -> None:
    d = COSDictionary()
    d.set_item(
        COSName.get_pdf_name("L"),
        COSArray(
            [
                COSFloat(1.0),
                COSFloat(2.0),
                COSFloat(3.0),
                COSFloat(4.0),
                COSFloat(999.0),
            ]
        ),
    )

    assert FDFAnnotationLine(d).get_line() == [1.0, 2.0, 3.0, 4.0]


def test_line_malformed_coordinate_array_reports_absent() -> None:
    d = COSDictionary()
    d.set_item(
        COSName.get_pdf_name("L"),
        COSArray(
            [
                COSInteger.get(1),
                COSName.get_pdf_name("Bad"),
                COSInteger.get(3),
                COSInteger.get(4),
            ]
        ),
    )
    a = FDFAnnotationLine(d)

    assert a.get_line() is None
    assert a.get_start_point() is None
    assert a.get_end_point() is None


def test_setting_only_end_point_initialises_start_zero() -> None:
    a = FDFAnnotationLine()
    a.set_end_point(5.0, 6.0)
    assert a.get_start_point() == (0.0, 0.0)
    assert a.get_end_point() == (5.0, 6.0)


def test_line_ending_styles_default_none() -> None:
    a = FDFAnnotationLine()
    assert a.get_start_point_ending_style() == FDFAnnotationLine.LE_NONE
    assert a.get_end_point_ending_style() == FDFAnnotationLine.LE_NONE
    a.set_start_point_ending_style(FDFAnnotationLine.LE_OPEN_ARROW)
    a.set_end_point_ending_style(FDFAnnotationLine.LE_CLOSED_ARROW)
    assert a.get_start_point_ending_style() == "OpenArrow"
    assert a.get_end_point_ending_style() == "ClosedArrow"


def test_interior_color_round_trip() -> None:
    a = FDFAnnotationLine()
    assert a.get_interior_color() is None
    a.set_interior_color((0.7, 0.8, 0.9))
    got = a.get_interior_color()
    assert got is not None
    assert got == pytest.approx((0.7, 0.8, 0.9), abs=1e-6)
    a.set_interior_color(None)
    assert a.get_interior_color() is None


def test_leader_lines_round_trip() -> None:
    a = FDFAnnotationLine()
    assert a.get_leader_line() == 0.0
    assert a.get_leader_line_extension() == 0.0
    assert a.get_leader_line_offset() == 0.0
    a.set_leader_line(5.0)
    a.set_leader_line_extension(3.5)
    a.set_leader_line_offset(1.25)
    assert a.get_leader_line() == 5.0
    assert a.get_leader_line_extension() == 3.5
    assert a.get_leader_line_offset() == 1.25


def test_caption_flag_default_false() -> None:
    a = FDFAnnotationLine()
    assert a.get_caption() is False
    a.set_caption(True)
    assert a.get_caption() is True


def test_intent_round_trip() -> None:
    a = FDFAnnotationLine()
    assert a.get_intent() is None
    a.set_intent("LineArrow")
    assert a.get_intent() == "LineArrow"
    a.set_intent(None)
    assert a.get_intent() is None


def test_caption_position_round_trip() -> None:
    a = FDFAnnotationLine()
    assert a.get_caption_position() is None
    a.set_caption_position("Inline")
    assert a.get_caption_position() == "Inline"
    a.set_caption_position(None)
    assert a.get_caption_position() is None


def test_caption_offset_round_trip() -> None:
    a = FDFAnnotationLine()
    assert a.get_caption_horizontal_offset() == 0.0
    assert a.get_caption_vertical_offset() == 0.0
    a.set_caption_horizontal_offset(2.5)
    a.set_caption_vertical_offset(-1.25)
    assert a.get_caption_horizontal_offset() == 2.5
    assert a.get_caption_vertical_offset() == -1.25


def test_factory_dispatch_line() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Line"))
    obj = FDFAnnotation.create(d)
    assert isinstance(obj, FDFAnnotationLine)


def test_factory_unknown_subtype_returns_base() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Highlight"))
    obj = FDFAnnotation.create(d)
    assert isinstance(obj, FDFAnnotation)
    assert not isinstance(obj, FDFAnnotationLine)
