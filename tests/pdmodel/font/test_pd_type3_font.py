"""Hand-written tests for the round-out methods on
:class:`pypdfbox.pdmodel.font.PDType3Font` (encoded ``get_char_proc``,
``get_width``, ``has_glyph``, ``is_embedded``).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
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


# ---------- get_name — Type 3 reads /Name, NOT /BaseFont ----------


def test_get_name_returns_name_entry_when_set() -> None:
    # Mirrors upstream PDType3Font.getName() ->
    # dict.getNameAsString(COSName.NAME): Type 3 fonts use the legacy
    # /Name entry, not /BaseFont.
    font = PDType3Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("Name"), "MyType3")
    assert font.get_name() == "MyType3"


def test_get_name_returns_none_when_name_absent() -> None:
    font = PDType3Font()
    assert font.get_name() is None


def test_get_name_ignores_basefont_for_type3() -> None:
    # /BaseFont must not leak into Type 3's get_name (upstream-divergent
    # historically; this asserts the corrected upstream-matching behavior).
    font = PDType3Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
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


# ---------- read_code (single-byte) ----------


def test_read_code_returns_single_byte() -> None:
    # Mirrors upstream PDType3Font.readCode -> in.read().
    font = PDType3Font()
    assert font.read_code(io.BytesIO(b"\x41")) == 0x41


def test_read_code_consumes_one_byte_of_stream() -> None:
    font = PDType3Font()
    stream = io.BytesIO(b"\x41\x42")
    assert font.read_code(stream) == 0x41
    assert font.read_code(stream) == 0x42


def test_read_code_raises_at_eof() -> None:
    font = PDType3Font()
    with pytest.raises(EOFError):
        font.read_code(io.BytesIO(b""))


# ---------- get_path / get_font_box_font / encode_codepoint / read_encoding_from_font ----------


def test_get_path_raises_not_implemented() -> None:
    # Mirrors upstream UnsupportedOperationException.
    font = PDType3Font()
    with pytest.raises(NotImplementedError):
        font.get_path("A")


def test_get_font_box_font_raises_not_implemented() -> None:
    font = PDType3Font()
    with pytest.raises(NotImplementedError):
        font.get_font_box_font()


def test_encode_codepoint_raises_not_implemented() -> None:
    font = PDType3Font()
    with pytest.raises(NotImplementedError):
        font.encode_codepoint(0x41)


def test_read_encoding_from_font_raises_not_implemented() -> None:
    font = PDType3Font()
    with pytest.raises(NotImplementedError):
        font.read_encoding_from_font()


# ---------- read_encoding (resolves /Encoding + GlyphList) ----------


def test_read_encoding_resolves_predefined_name() -> None:
    font, _ = _make_font_with_glyph(0x41, "A")
    # Should not raise and should prime the typed encoding cache.
    font.read_encoding()
    assert isinstance(font.get_encoding_typed(), WinAnsiEncoding)


def test_read_encoding_no_op_when_encoding_absent() -> None:
    font = PDType3Font()
    font.read_encoding()
    # No /Encoding -> typed encoding stays None; no exception.
    assert font.get_encoding_typed() is None


# ---------- is_standard14 (Java-cased alias) ----------


def test_is_standard14_alias_returns_false() -> None:
    # Mirrors upstream PDType3Font.isStandard14() == false directly.
    font = PDType3Font()
    assert font.is_standard14() is False


def test_is_standard14_false_even_with_basefont_helvetica() -> None:
    # Type 3 with a Standard 14-looking /BaseFont still returns False.
    font = PDType3Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.is_standard14() is False


# ---------- check_font_matrix_values ----------


def test_check_font_matrix_values_accepts_six_numerics() -> None:
    arr = COSArray(
        [
            COSFloat(0.001),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(0.001),
            COSFloat(0.0),
            COSFloat(0.0),
        ]
    )
    assert PDType3Font.check_font_matrix_values(arr) is True


def test_check_font_matrix_values_rejects_wrong_size() -> None:
    arr = COSArray([COSFloat(1.0), COSFloat(0.0)])
    assert PDType3Font.check_font_matrix_values(arr) is False


def test_check_font_matrix_values_rejects_none() -> None:
    assert PDType3Font.check_font_matrix_values(None) is False


def test_check_font_matrix_values_rejects_non_numeric_entry() -> None:
    arr = COSArray(
        [
            COSFloat(1.0),
            COSFloat(0.0),
            COSName.get_pdf_name("not-a-number"),
            COSFloat(1.0),
            COSFloat(0.0),
            COSFloat(0.0),
        ]
    )
    assert PDType3Font.check_font_matrix_values(arr) is False


# ---------- generate_bounding_box (CharProcs union plan-B) ----------


def test_get_bounding_box_returns_font_bbox_when_non_zero() -> None:
    font = PDType3Font()
    rect = PDRectangle(0.0, -200.0, 750.0, 900.0)
    font.set_font_bbox(rect)
    out = font.get_bounding_box()
    assert out is not None
    assert out == rect


def test_get_bounding_box_unions_charproc_bboxes_when_font_bbox_zero() -> None:
    # Mirrors upstream generateBoundingBox plan-B: when /FontBBox is the
    # all-zero default, expand by unioning every /CharProcs glyph bbox
    # (d1 operands).
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 0.0, 0.0))

    char_procs = COSDictionary()
    glyph_a = COSStream()
    # "wx wy llx lly urx ury d1" -> bbox = [-10, -20, 700, 900]
    glyph_a.set_raw_data(b"600 0 -10 -20 700 900 d1\n")
    char_procs.set_item(COSName.get_pdf_name("A"), glyph_a)

    glyph_b = COSStream()
    # bbox = [50, -50, 800, 1000]; union -> [-10, -50, 800, 1000]
    glyph_b.set_raw_data(b"600 0 50 -50 800 1000 d1\n")
    char_procs.set_item(COSName.get_pdf_name("B"), glyph_b)
    font.set_char_procs(char_procs)

    out = font.get_bounding_box()
    assert out is not None
    assert out.get_lower_left_x() == pytest.approx(-10.0)
    assert out.get_lower_left_y() == pytest.approx(-50.0)
    assert out.get_upper_right_x() == pytest.approx(800.0)
    assert out.get_upper_right_y() == pytest.approx(1000.0)


def test_get_bounding_box_returns_zero_rect_when_charprocs_missing() -> None:
    # /FontBBox present but zero, no /CharProcs -> upstream returns the
    # zero rect itself (no union to apply).
    font = PDType3Font()
    rect = PDRectangle(0.0, 0.0, 0.0, 0.0)
    font.set_font_bbox(rect)
    out = font.get_bounding_box()
    assert out is not None
    assert out == rect


def test_get_bounding_box_caches_result() -> None:
    # Second call must return the same object (memoised, like upstream's
    # ``fontBBox`` field).
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 100.0, 200.0))
    first = font.get_bounding_box()
    second = font.get_bounding_box()
    assert first is second


def test_get_bounding_box_skips_d0_charprocs_in_union() -> None:
    # d0 declares no bbox -> get_glyph_bbox returns None -> upstream
    # continues without expanding the rect.
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 0.0, 0.0))

    char_procs = COSDictionary()
    glyph = COSStream()
    glyph.set_raw_data(b"600 0 d0\n")  # d0, no bbox
    char_procs.set_item(COSName.get_pdf_name("A"), glyph)
    font.set_char_procs(char_procs)

    out = font.get_bounding_box()
    assert out is not None
    # All-zero in -> all-zero out (no glyph bbox to absorb).
    assert out.get_lower_left_x() == 0.0
    assert out.get_upper_right_x() == 0.0


# ---------- generate_bounding_box (public, bypasses cache) ----------


def test_generate_bounding_box_returns_none_when_font_bbox_missing() -> None:
    # Mirrors upstream private generateBoundingBox: with no /FontBBox at
    # all the helper returns None (caller's "warning + empty bbox" path).
    font = PDType3Font()
    assert font.generate_bounding_box() is None


def test_generate_bounding_box_does_not_consult_cache() -> None:
    # The public helper is the cache miss path — every call recomputes.
    font = PDType3Font()
    font.set_font_bbox(PDRectangle(0.0, 0.0, 100.0, 200.0))
    a = font.generate_bounding_box()
    b = font.generate_bounding_box()
    assert a == b
    # And distinct instances (not memoised).
    assert a is not b


# ---------- is_damaged override ----------


def test_is_damaged_explicit_override_returns_false() -> None:
    # Mirrors upstream PDType3Font.isDamaged(): no font program to load,
    # so no parse step that could fail. The override is declared on the
    # subclass for parity with upstream's explicit override.
    font = PDType3Font()
    assert font.is_damaged() is False
    # Method must be defined on PDType3Font itself, not just inherited.
    assert "is_damaged" in PDType3Font.__dict__


