from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSObject,
    COSString,
)
from pypdfbox.pdmodel.fdf import FDFAnnotationCircle, FDFAnnotationLine, FDFDictionary


def test_wave765_line_start_point_pads_short_line_array() -> None:
    annotation = COSDictionary()
    annotation.set_item(
        COSName.get_pdf_name("L"),
        COSArray([COSFloat(10.0), COSFloat(20.0)]),
    )

    line = FDFAnnotationLine(annotation)
    line.set_start_point(1.5, 2.5)

    raw = annotation.get_dictionary_object(COSName.get_pdf_name("L"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 4
    assert line.get_line() == [1.5, 2.5, 0.0, 0.0]


def test_wave765_line_end_style_pads_existing_short_ending_array() -> None:
    annotation = COSDictionary()
    annotation.set_item(
        COSName.get_pdf_name("LE"),
        COSArray([COSName.get_pdf_name(FDFAnnotationLine.LE_OPEN_ARROW)]),
    )

    line = FDFAnnotationLine(annotation)
    line.set_end_point_ending_style(FDFAnnotationLine.LE_SLASH)

    assert line.get_start_point_ending_style() == FDFAnnotationLine.LE_OPEN_ARROW
    assert line.get_end_point_ending_style() == FDFAnnotationLine.LE_SLASH


def test_wave765_caption_vertical_offset_pads_existing_empty_array() -> None:
    annotation = COSDictionary()
    annotation.set_item(COSName.get_pdf_name("CO"), COSArray())

    line = FDFAnnotationLine(annotation)
    line.set_caption_vertical_offset(6.25)

    assert line.get_caption_horizontal_offset() == 0.0
    assert line.get_caption_vertical_offset() == pytest.approx(6.25, abs=1e-6)


def test_wave765_caption_offsets_default_for_unresolved_or_non_numeric_entries() -> None:
    annotation = COSDictionary()
    annotation.set_item(
        COSName.get_pdf_name("CO"),
        COSArray(
            [
                COSObject(7),
                COSName.get_pdf_name("NotANumber"),
            ]
        ),
    )

    line = FDFAnnotationLine(annotation)

    assert line.get_caption_horizontal_offset() == 0.0
    assert line.get_caption_vertical_offset() == 0.0


def test_wave765_circle_malformed_numeric_fringe_reports_absent() -> None:
    circle = FDFAnnotationCircle()
    circle.get_cos_object().set_item(
        COSName.get_pdf_name("RD"),
        COSArray(
            [
                COSFloat(0.0),
                COSName.get_pdf_name("Bad"),
                COSFloat(10.0),
                COSFloat(20.0),
            ]
        ),
    )

    assert circle.get_fringe() is None


def test_wave765_dictionary_set_file_accepts_raw_cosbase_and_file_path_swallows_error() -> None:
    fdf = FDFDictionary()
    raw = COSArray()

    fdf.set_file(raw)

    assert fdf.has_file()
    assert fdf.get_cos_object().get_dictionary_object(COSName.get_pdf_name("F")) is raw
    with pytest.raises(OSError):
        fdf.get_file()
    assert fdf.get_file_path() is None


def test_wave765_dictionary_get_encoding_accepts_legacy_string_entry() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Encoding"), COSString("UTF-16BE"))

    fdf = FDFDictionary(raw)

    assert fdf.get_encoding() == "UTF-16BE"
