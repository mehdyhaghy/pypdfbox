"""Wave 279 coverage for Type 3 font convenience accessors."""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_resources import PDResources

_CHAR_PROCS = COSName.get_pdf_name("CharProcs")
_ENCODING = COSName.get_pdf_name("Encoding")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_FONT_BBOX = COSName.get_pdf_name("FontBBox")
_FONT_MATRIX = COSName.get_pdf_name("FontMatrix")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_RESOURCES = COSName.get_pdf_name("Resources")
_WIDTHS = COSName.get_pdf_name("Widths")


def _font_with_encoded_a(body: bytes = b"500 0 d0\n") -> tuple[PDType3Font, COSStream]:
    font = PDType3Font()
    font.get_cos_object().set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    glyph = COSStream()
    glyph.set_raw_data(body)
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("A"), glyph)
    font.set_char_procs(char_procs)
    return font, glyph


def test_clearable_metric_setters_restore_missing_entry_defaults() -> None:
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(66)
    font.set_widths([500.0, 600.0])
    font.set_font_matrix([0.002, 0.0, 0.0, 0.002, 1.0, 2.0])

    assert font.get_first_char() == 65
    assert font.get_last_char() == 66
    assert font.get_widths() == pytest.approx([500.0, 600.0])
    assert font.get_font_matrix() == pytest.approx(
        [0.002, 0.0, 0.0, 0.002, 1.0, 2.0], rel=1e-6
    )

    font.set_first_char(None)
    font.set_last_char(None)
    font.set_widths(None)
    font.set_font_matrix(None)

    cos = font.get_cos_object()
    assert cos.contains_key(_FIRST_CHAR) is False
    assert cos.contains_key(_LAST_CHAR) is False
    assert cos.contains_key(_WIDTHS) is False
    assert cos.contains_key(_FONT_MATRIX) is False
    assert font.get_first_char() == -1
    assert font.get_last_char() == -1
    assert font.get_widths() == []
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_type3_font_cos_round_trip_preserves_owned_dictionaries() -> None:
    raw = COSDictionary()
    raw.set_int(_FIRST_CHAR, 65)
    raw.set_int(_LAST_CHAR, 65)
    raw.set_item(_WIDTHS, COSArray([COSInteger.get(625)]))
    raw.set_item(
        _FONT_MATRIX,
        COSArray(
            [
                COSFloat(0.002),
                COSInteger.get(0),
                COSInteger.get(0),
                COSFloat(0.002),
                COSFloat(10.0),
                COSFloat(-3.5),
            ]
        ),
    )
    raw.set_item(
        _FONT_BBOX,
        COSArray(
            [
                COSInteger.get(-10),
                COSInteger.get(-20),
                COSInteger.get(700),
                COSInteger.get(900),
            ]
        ),
    )
    resources = COSDictionary()
    raw.set_item(_RESOURCES, resources)
    glyph = COSStream()
    glyph.set_raw_data(b"625 0 -10 -20 700 900 d1\n")
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("A"), glyph)
    raw.set_item(_CHAR_PROCS, char_procs)
    raw.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))

    font = PDType3Font(raw)

    assert font.get_first_char() == 65
    assert font.get_last_char() == 65
    assert font.get_widths() == [625.0]
    assert font.get_font_matrix() == pytest.approx(
        [0.002, 0.0, 0.0, 0.002, 10.0, -3.5], rel=1e-6
    )
    assert font.get_font_b_box() is raw.get_dictionary_object(_FONT_BBOX)
    assert font.get_resources().get_cos_object() is resources  # type: ignore[union-attr]
    assert font.get_char_procs() is char_procs
    assert font.get_char_proc("A") is glyph

    proc = font.get_char_proc(65)
    assert isinstance(proc, PDType3CharProc)
    # Upstream getContentStream() returns a fresh PDStream wrapper around
    # the same COSStream — assert we're wrapping the right glyph stream.
    assert proc.get_content_stream().get_cos_object() is glyph
    assert proc.get_cos_object() is glyph
    assert proc.get_width() == pytest.approx(625.0)
    glyph_bbox = proc.get_glyph_bbox()
    assert glyph_bbox is not None
    assert glyph_bbox.get_lower_left_x() == pytest.approx(-10.0)
    assert glyph_bbox.get_upper_right_y() == pytest.approx(900.0)


def test_type3_font_ignores_malformed_top_level_shapes() -> None:
    font = PDType3Font()
    cos = font.get_cos_object()
    cos.set_int(_CHAR_PROCS, 7)
    cos.set_int(_RESOURCES, 8)
    cos.set_item(_FONT_BBOX, COSArray([COSInteger.get(0), COSInteger.get(1)]))
    cos.set_item(
        _FONT_MATRIX,
        COSArray(
            [
                COSFloat(1.0),
                COSFloat(0.0),
                COSName.get_pdf_name("not-a-number"),
                COSFloat(1.0),
                COSFloat(0.0),
                COSFloat(0.0),
            ]
        ),
    )
    cos.set_item(
        _WIDTHS,
        COSArray(
            [
                COSInteger.get(250),
                COSName.get_pdf_name("bad-width"),
                COSFloat(333.5),
            ]
        ),
    )

    assert font.get_char_procs() is None
    assert font.get_char_proc("A") is None
    assert font.get_resources() is None
    # Upstream getFontBBox() builds a PDRectangle from ANY COSArray: a short
    # [0, 1] array is zero-padded to four ([0, 1, 0, 0]) and the corners
    # normalise via min/max -> (0, 0, 0, 1). Pinned live by
    # tests/pdmodel/font/oracle/test_type3_font_fuzz_wave1522.py (bbox_len2).
    bbox = font.get_font_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 0.0
    assert bbox.get_lower_left_y() == 0.0
    assert bbox.get_upper_right_x() == 0.0
    assert bbox.get_upper_right_y() == 1.0
    assert font.get_font_b_box() is cos.get_dictionary_object(_FONT_BBOX)
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    # Upstream COSArray.toCOSNumberFloatList keeps a None slot for the
    # non-numeric "bad-width" entry (index alignment preserved) — see the
    # live oracle in tests/pdmodel/font/oracle/test_simple_font_widths_oracle.py
    # (wave 1469).
    widths = font.get_widths()
    assert len(widths) == 3
    assert widths[0] == pytest.approx(250.0)
    assert widths[1] is None
    assert widths[2] == pytest.approx(333.5)


def test_char_proc_malformed_local_resources_falls_back_to_font_resources() -> None:
    font, glyph = _font_with_encoded_a()
    resources = PDResources()
    font.set_resources(resources)
    glyph.set_item(_RESOURCES, COSName.get_pdf_name("NotADictionary"))

    proc = font.get_char_proc(65)

    assert isinstance(proc, PDType3CharProc)
    assert proc.has_resources() is True
    assert proc.get_resources().get_cos_object() is resources.get_cos_object()  # type: ignore[union-attr]


def test_char_proc_content_stream_accessors_stay_on_underlying_stream() -> None:
    font, glyph = _font_with_encoded_a(b"480 0 d0\nq Q\n")

    proc = font.get_char_proc(65)

    assert isinstance(proc, PDType3CharProc)
    # Upstream getContentStream() returns a fresh PDStream wrapper around
    # the underlying COSStream; the COS-level identity is what survives.
    assert proc.get_content_stream().get_cos_object() is glyph
    assert proc.get_cos_object() is glyph
    with proc.get_contents() as contents:
        assert contents.read() == b"480 0 d0\nq Q\n"
    assert font.get_width_from_font(65) == pytest.approx(480.0)
