"""Hand-written tests for the round-out methods on
:class:`pypdfbox.pdmodel.font.PDType3Font` (encoded ``get_char_proc``,
``get_width``, ``has_glyph``, ``is_embedded``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font import PDFontLike
from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------- get_char_proc(int code) -- typed wrapper ----------


def _make_font_with_glyph(code: int, glyph_name: str) -> tuple[PDType3Font, COSStream]:
    """Helper: build a Type 3 font with WinAnsi encoding and one glyph
    stream registered under ``glyph_name``."""
    font = PDType3Font()
    # Wire WinAnsi as the encoding (a real PostScript encoding name).
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    char_procs = COSDictionary()
    glyph = COSStream()
    char_procs.set_item(COSName.get_pdf_name(glyph_name), glyph)
    font.set_char_procs(char_procs)
    return font, glyph


def test_get_char_proc_by_code_returns_typed_wrapper() -> None:
    # WinAnsi maps 0x41 ('A') to glyph name "A".
    font, glyph_stream = _make_font_with_glyph(0x41, "A")
    proc = font.get_char_proc(0x41)
    assert isinstance(proc, PDType3CharProc)
    # The wrapper holds the same underlying COSStream.
    assert proc.get_cos_object() is glyph_stream
    # And the back-pointer to the parent font is wired.
    assert proc.get_font() is font


def test_get_char_proc_by_code_returns_none_when_no_encoding() -> None:
    font = PDType3Font()
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("A"), COSStream())
    font.set_char_procs(char_procs)
    # No /Encoding -> can't map code to name -> None.
    assert font.get_char_proc(0x41) is None


def test_get_char_proc_by_code_returns_none_for_unmapped_code() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    # Code 0x00 maps to ".notdef" in WinAnsi -> None.
    assert font.get_char_proc(0x00) is None


def test_get_char_proc_by_code_returns_none_when_charprocs_missing_entry() -> None:
    # WinAnsi maps 0x42 to 'B', but only 'A' is in /CharProcs.
    font, _ = _make_font_with_glyph(0x41, "A")
    assert font.get_char_proc(0x42) is None


def test_get_char_proc_str_form_still_returns_raw_stream() -> None:
    # The legacy str-keyed form must keep returning the raw COSStream
    # (parity tests rely on identity comparison).
    font, glyph_stream = _make_font_with_glyph(0x41, "A")
    assert font.get_char_proc("A") is glyph_stream


def test_get_char_proc_rejects_bool() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    with pytest.raises(TypeError):
        font.get_char_proc(True)


# ---------- get_width(code) ----------


def test_get_width_returns_widths_entry_offset_by_first_char() -> None:
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(67)
    font.set_widths([500.0, 600.0, 700.0])
    assert font.get_width(65) == pytest.approx(500.0)
    assert font.get_width(66) == pytest.approx(600.0)
    assert font.get_width(67) == pytest.approx(700.0)


def test_get_width_returns_zero_for_code_below_first_char() -> None:
    font = PDType3Font()
    font.set_first_char(65)
    font.set_widths([500.0, 600.0])
    assert font.get_width(64) == 0.0


def test_get_width_returns_zero_for_code_beyond_widths_array() -> None:
    font = PDType3Font()
    font.set_first_char(65)
    font.set_widths([500.0, 600.0])
    assert font.get_width(67) == 0.0


def test_get_width_returns_zero_when_no_widths_array() -> None:
    font = PDType3Font()
    assert font.get_width(0x41) == 0.0


def test_get_width_zero_when_first_and_last_char_both_missing() -> None:
    # No /FirstChar / /LastChar (both default to -1) -> the
    # "code >= firstChar && code <= lastChar" gate fails for code 0
    # (0 <= -1 is false), so upstream falls through to /MissingWidth /
    # getWidthFromFont. With no descriptor and no /CharProcs we end at
    # 0.0. Mirrors upstream PDType3Font.getWidth.
    font = PDType3Font()
    font.set_widths([100.0, 200.0, 300.0])
    assert font.get_width(0) == 0.0


# ---------- has_glyph ----------


def test_has_glyph_true_when_encoding_and_charproc_both_present() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    assert font.has_glyph(0x41) is True


def test_has_glyph_false_when_charproc_missing() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    # 0x42 -> "B", but /CharProcs only has "A".
    assert font.has_glyph(0x42) is False


def test_has_glyph_false_when_no_encoding() -> None:
    font = PDType3Font()
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("A"), COSStream())
    font.set_char_procs(char_procs)
    assert font.has_glyph(0x41) is False


def test_has_glyph_false_for_notdef_code() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    # WinAnsi maps 0x00 to ".notdef".
    assert font.has_glyph(0x00) is False


# ---------- is_embedded ----------


def test_is_embedded_always_true() -> None:
    # Type 3 fonts have no font program — they're inline by definition.
    font = PDType3Font()
    assert font.is_embedded() is True


def test_is_embedded_true_even_without_font_descriptor() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    # Sanity: there's no /FontDescriptor at all.
    assert font.get_font_descriptor() is None
    assert font.is_embedded() is True


# ---------- is_damaged inherits PDFont default (False) ----------


def test_is_damaged_default_false() -> None:
    font = PDType3Font()
    assert font.is_damaged() is False


# ---------- get_name (inherited /BaseFont) ----------


def test_get_name_returns_basefont_when_set() -> None:
    font = PDType3Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "MyType3")
    assert font.get_name() == "MyType3"


def test_get_name_returns_none_when_basefont_absent() -> None:
    font = PDType3Font()
    assert font.get_name() is None


# ---------- PDFontLike parity surface ----------


def test_get_bounding_box_delegates_to_font_bbox() -> None:
    font = PDType3Font()
    rect = PDRectangle(0.0, -200.0, 750.0, 900.0)
    font.set_font_bbox(rect)

    assert font.get_bounding_box() == rect


def test_get_bounding_box_returns_none_when_font_bbox_missing() -> None:
    assert PDType3Font().get_bounding_box() is None


def test_get_position_vector_is_horizontal_zero_vector() -> None:
    font = PDType3Font()

    assert font.get_position_vector(0x41) == (0.0, 0.0)


def test_type3_font_satisfies_font_like_protocol() -> None:
    assert isinstance(PDType3Font(), PDFontLike)


# ---------- get_encoding (raw) ----------


def test_get_encoding_returns_cos_name_for_predefined() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    raw = font.get_encoding()
    assert isinstance(raw, COSName)
    assert raw.get_name() == "WinAnsiEncoding"


def test_get_encoding_typed_resolves_to_winansi() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    typed = font.get_encoding_typed()
    assert isinstance(typed, WinAnsiEncoding)


# ---------- get_width fallback to /MissingWidth ----------


def test_get_width_falls_back_to_missing_width_when_descriptor_present() -> None:
    # /Widths covers 65..66 only; code 70 is outside the range, so
    # upstream falls through to the descriptor's /MissingWidth.
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(66)
    font.set_widths([500.0, 600.0])
    descriptor = PDFontDescriptor()
    descriptor.set_missing_width(250.0)
    font.set_font_descriptor(descriptor)
    assert font.get_width(70) == pytest.approx(250.0)


def test_get_width_uses_missing_width_when_widths_empty() -> None:
    # No /Widths at all — the gate fails, and we land on /MissingWidth.
    font = PDType3Font()
    descriptor = PDFontDescriptor()
    descriptor.set_missing_width(333.0)
    font.set_font_descriptor(descriptor)
    assert font.get_width(0x41) == pytest.approx(333.0)


def test_get_width_in_range_wins_over_missing_width() -> None:
    # When the code IS in the FirstChar..LastChar window, /Widths wins
    # — /MissingWidth is only consulted on out-of-range codes.
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(66)
    font.set_widths([500.0, 600.0])
    descriptor = PDFontDescriptor()
    descriptor.set_missing_width(999.0)
    font.set_font_descriptor(descriptor)
    assert font.get_width(65) == pytest.approx(500.0)
    assert font.get_width(66) == pytest.approx(600.0)


def test_get_width_zero_when_in_range_but_widths_array_short() -> None:
    # /FirstChar=65 /LastChar=70 but only two width entries — codes
    # 67..70 fall in-range yet past the array end -> upstream returns 0.
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(70)
    font.set_widths([500.0, 600.0])
    assert font.get_width(67) == 0.0


# ---------- get_width_from_font ----------


def test_get_width_from_font_zero_for_unmapped_code() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    # 0x42 -> 'B' but no /CharProcs entry for it.
    assert font.get_width_from_font(0x42) == 0.0


def test_get_width_from_font_zero_for_empty_charproc_stream() -> None:
    # Empty content stream -> upstream short-circuits to 0 without
    # parsing the (non-existent) glyph metric op.
    font, glyph = _make_font_with_glyph(0x41, "A")
    # The default COSStream has zero length already, but verify.
    assert glyph.get_length() == 0
    assert font.get_width_from_font(0x41) == 0.0


def test_get_width_from_font_reads_metric_op_from_charproc() -> None:
    # Construct a CharProc with a "500 0 d0" header — the d0 / d1
    # operators are the only carriers of glyph width info.
    font = PDType3Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    char_procs = COSDictionary()
    glyph = COSStream()
    glyph.set_raw_data(b"500 0 d0\n")
    char_procs.set_item(COSName.get_pdf_name("A"), glyph)
    font.set_char_procs(char_procs)
    assert font.get_width_from_font(0x41) == pytest.approx(500.0)


# ---------- get_height ----------


def test_get_height_zero_when_no_descriptor() -> None:
    font = PDType3Font()
    assert font.get_height(0x41) == 0.0


def test_get_height_uses_half_of_font_bbox() -> None:
    # /FontBBox is the first source — upstream uses height/2 as the
    # representative glyph height (an empirical approximation; see
    # the comment block above PDType3Font.getHeight in upstream).
    font = PDType3Font()
    descriptor = PDFontDescriptor()
    # bbox height = 800; expect 400.
    descriptor.set_font_bounding_box(PDRectangle(0.0, -200.0, 1000.0, 600.0))
    font.set_font_descriptor(descriptor)
    assert font.get_height(0x41) == pytest.approx(400.0)


def test_get_height_falls_back_to_cap_height() -> None:
    font = PDType3Font()
    descriptor = PDFontDescriptor()
    # No bbox -> next try /CapHeight.
    descriptor.set_cap_height(700.0)
    font.set_font_descriptor(descriptor)
    assert font.get_height(0x41) == pytest.approx(700.0)


def test_get_height_falls_back_to_ascent() -> None:
    font = PDType3Font()
    descriptor = PDFontDescriptor()
    # No bbox, cap_height defaults to 0 -> next /Ascent.
    descriptor.set_ascent(750.0)
    font.set_font_descriptor(descriptor)
    assert font.get_height(0x41) == pytest.approx(750.0)


def test_get_height_falls_back_to_x_height_minus_descent() -> None:
    font = PDType3Font()
    descriptor = PDFontDescriptor()
    descriptor.set_x_height(500.0)
    descriptor.set_descent(-200.0)  # descents are conventionally negative
    font.set_font_descriptor(descriptor)
    # 500 - (-200) = 700.
    assert font.get_height(0x41) == pytest.approx(700.0)


def test_get_height_zero_when_x_height_zero() -> None:
    # /XHeight = 0 must NOT trigger the x_height-descent branch
    # (otherwise we'd return -descent, which is wrong).
    font = PDType3Font()
    descriptor = PDFontDescriptor()
    descriptor.set_descent(-200.0)
    font.set_font_descriptor(descriptor)
    assert font.get_height(0x41) == 0.0


def test_get_height_skips_zero_bbox() -> None:
    # A degenerate bbox (height 0) must not short-circuit — upstream
    # checks ``Float.compare(retval, 0) == 0`` after each step.
    font = PDType3Font()
    descriptor = PDFontDescriptor()
    descriptor.set_font_bounding_box(PDRectangle(0.0, 0.0, 100.0, 0.0))
    descriptor.set_cap_height(600.0)
    font.set_font_descriptor(descriptor)
    assert font.get_height(0x41) == pytest.approx(600.0)


# ---------- get_displacement ----------


def test_get_displacement_default_matrix_scales_by_thousandth() -> None:
    # Default /FontMatrix is [0.001, 0, 0, 0.001, 0, 0]; displacement
    # of (width, 0) -> (width / 1000, 0).
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(65)
    font.set_widths([500.0])
    tx, ty = font.get_displacement(65)
    assert tx == pytest.approx(0.5)
    assert ty == pytest.approx(0.0)


def test_get_displacement_custom_matrix_applies_horizontal_scale() -> None:
    # Per PDFBOX-2298, some Type 3 fonts ship a custom /FontMatrix.
    # With [0.002, 0, 0, 0.002, 0, 0] the displacement of (width, 0)
    # becomes (width * 0.002, 0).
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(65)
    font.set_widths([500.0])
    font.set_font_matrix([0.002, 0.0, 0.0, 0.002, 0.0, 0.0])
    tx, ty = font.get_displacement(65)
    assert tx == pytest.approx(1.0)
    assert ty == pytest.approx(0.0)


def test_get_displacement_zero_for_unmapped_code() -> None:
    # No /Widths and no /FontDescriptor and no /CharProcs ->
    # get_width(code) is 0 -> displacement is (0, 0).
    font = PDType3Font()
    assert font.get_displacement(0x41) == (0.0, 0.0)
