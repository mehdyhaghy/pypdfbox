"""Hand-written tests for the pdmodel ``WinAnsiEncoding`` wrapper.

WinAnsi is a CP1252 superset; per the PDF spec all unused codes greater
than octal 040 fall back to the ``bullet`` glyph. These tests exercise
that behavior plus the standard pdmodel surface.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import Encoding, WinAnsiEncoding


def test_singleton_identity():
    assert WinAnsiEncoding.INSTANCE is WinAnsiEncoding.INSTANCE
    assert isinstance(WinAnsiEncoding.INSTANCE, WinAnsiEncoding)


def test_encoding_name():
    assert WinAnsiEncoding.INSTANCE.get_encoding_name() == "WinAnsiEncoding"


def test_get_cos_object():
    cos = WinAnsiEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "WinAnsiEncoding"


def test_uppercase_letters():
    enc = WinAnsiEncoding.INSTANCE
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert enc.get_name(ord(ch)) == ch


def test_lowercase_letters():
    enc = WinAnsiEncoding.INSTANCE
    for ch in "abcdefghijklmnopqrstuvwxyz":
        assert enc.get_name(ord(ch)) == ch


def test_digits():
    enc = WinAnsiEncoding.INSTANCE
    digits = ["zero", "one", "two", "three", "four",
              "five", "six", "seven", "eight", "nine"]
    for i, name in enumerate(digits):
        assert enc.get_name(0x30 + i) == name


def test_extended_punctuation():
    enc = WinAnsiEncoding.INSTANCE
    # Selected CP1252 glyphs.
    assert enc.get_name(0x80) == "Euro"
    assert enc.get_name(0xA9) == "copyright"
    assert enc.get_name(0xAE) == "registered"


def test_unmapped_high_codes_fall_back_to_bullet():
    # Per the PDF spec, codes > 040 octal that aren't in the explicit table
    # fall back to ``bullet`` (not ``.notdef``).
    enc = WinAnsiEncoding.INSTANCE
    # 0x81, 0x8D, 0x8F, 0x90, 0x9D — gaps in CP1252 that PDFBox fills with bullet.
    assert enc.get_name(0x81) == "bullet"
    assert enc.get_name(0x8D) == "bullet"


def test_low_control_codes_remain_notdef():
    # Codes <= 040 octal stay unmapped (not bullet).
    enc = WinAnsiEncoding.INSTANCE
    assert enc.get_name(0x01) == ".notdef"
    assert enc.get_name(0x1F) == ".notdef"


def test_round_trip_get_code():
    enc = WinAnsiEncoding.INSTANCE
    assert enc.get_code("A") == 0x41
    assert enc.get_code("Euro") == 0x80


def test_factory_resolves_to_singleton():
    assert Encoding.get_instance("WinAnsiEncoding") is WinAnsiEncoding.INSTANCE
    name = COSName.get_pdf_name("WinAnsiEncoding")
    assert Encoding.get_instance(name) is WinAnsiEncoding.INSTANCE


def test_table_size_is_complete():
    # Every code from 0x21 (octal 041) through 0xFF must resolve to a glyph
    # name (either explicit or the ``bullet`` fallback) — never ``.notdef``.
    enc = WinAnsiEncoding.INSTANCE
    for code in range(0o41, 256):
        assert enc.get_name(code) != ".notdef", f"code {code:#x} unresolved"
