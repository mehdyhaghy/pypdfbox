"""Hand-written tests for the round-out methods on
:class:`pypdfbox.pdmodel.font.PDType3Font` (encoded ``get_char_proc``,
``get_width``, ``has_glyph``, ``is_embedded``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font


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
        font.get_char_proc(True)  # type: ignore[arg-type]


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


def test_get_width_treats_missing_first_char_as_zero() -> None:
    # No /FirstChar (defaults to -1) -> upstream falls back to 0 base.
    font = PDType3Font()
    font.set_widths([100.0, 200.0, 300.0])
    assert font.get_width(0) == pytest.approx(100.0)
    assert font.get_width(2) == pytest.approx(300.0)


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
