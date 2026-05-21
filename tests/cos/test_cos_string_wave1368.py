"""Wave 1368 — COSString byte vs text round-trips and hex form parity.

Round-out tests for paths not yet covered:

* ``COSString(str)`` constructor coerces a unicode payload into UTF-16BE
  with BOM when the string contains code points outside PDFDocEncoding;
  PDFDocEncoding when every code point fits.
* ``get_string`` decodes via UTF-16BE BOM, UTF-16LE BOM, UTF-8 BOM, and
  the PDFDocEncoding fallback.
* ``get_ascii`` substitutes ``?`` for high bytes (PDFBox parity with
  ``new String(bytes, US_ASCII)``).
* ``parse_hex`` accepts odd-length input (implicit trailing ``0``), with
  leading/trailing whitespace, and rejects internal whitespace unless
  ``FORCE_PARSING`` is set.
* ``to_hex_string`` emits uppercase hex.
* ``equals``/``hash_code`` match raw byte equality and ``forceHexForm``
  flag.
* ``set_value`` replaces the raw bytes.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSString

# ---------- str-constructor coercion ----------


def test_string_constructor_uses_pdfdoc_encoding_for_ascii_text() -> None:
    s = COSString("hello world")
    # PDFDocEncoding overlaps with ASCII for these characters.
    assert s.get_bytes() == b"hello world"
    assert s.get_string() == "hello world"


def test_string_constructor_uses_utf16be_with_bom_for_non_pdfdoc_text() -> None:
    s = COSString("héllo ☃")  # snowman is outside PDFDocEncoding
    raw = s.get_bytes()
    assert raw.startswith(b"\xfe\xff")
    assert s.get_string() == "héllo ☃"


def test_string_constructor_accepts_bytearray() -> None:
    s = COSString(bytearray(b"hello"))
    assert s.get_bytes() == b"hello"


def test_string_constructor_accepts_memoryview() -> None:
    s = COSString(memoryview(b"hello"))
    assert s.get_bytes() == b"hello"


# ---------- get_string BOM dispatch ----------


def test_get_string_utf16_be_bom_decodes_as_utf16be() -> None:
    payload = b"\xfe\xff" + "café".encode("utf-16-be")
    s = COSString(payload)
    assert s.get_string() == "café"


def test_get_string_utf16_le_bom_decodes_as_utf16le() -> None:
    payload = b"\xff\xfe" + "café".encode("utf-16-le")
    s = COSString(payload)
    assert s.get_string() == "café"


def test_get_string_utf8_bom_decodes_as_utf8() -> None:
    payload = b"\xef\xbb\xbf" + "café".encode("utf-8")
    s = COSString(payload)
    assert s.get_string() == "café"


def test_get_string_no_bom_decodes_as_pdfdoc_encoding() -> None:
    s = COSString(b"ABC")
    assert s.get_string() == "ABC"


# ---------- get_ascii ----------


def test_get_ascii_substitutes_question_for_high_bytes() -> None:
    s = COSString(bytes([0x41, 0xFF, 0x42, 0xC3]))
    # ASCII range survives; non-ASCII bytes become '?'.
    decoded = s.get_ascii()
    assert decoded[0] == "A"
    assert decoded[1] == "?"
    assert decoded[2] == "B"
    assert decoded[3] == "?"


def test_get_ascii_pure_ascii_passthrough() -> None:
    s = COSString(b"hello")
    assert s.get_ascii() == "hello"


# ---------- parse_hex ----------


def test_parse_hex_round_trip_basic() -> None:
    s = COSString.parse_hex("48656C6C6F")
    assert s.get_bytes() == b"Hello"


def test_parse_hex_strips_leading_and_trailing_whitespace() -> None:
    s = COSString.parse_hex("  48656C6C6F  ")
    assert s.get_bytes() == b"Hello"


def test_parse_hex_odd_length_pads_trailing_zero() -> None:
    # ``9`` → ``90``
    s = COSString.parse_hex("9")
    assert s.get_bytes() == b"\x90"


def test_parse_hex_rejects_internal_whitespace_by_default() -> None:
    with pytest.raises(OSError):
        COSString.parse_hex("48 65")


def test_parse_hex_substitutes_question_when_force_parsing_enabled() -> None:
    original = COSString.FORCE_PARSING
    try:
        COSString.FORCE_PARSING = True
        # "48656C" has length 6 (even) — body pairs are "48", "65", "6C".
        # Inject malformed pair: "48 56C" → length 6, pairs are
        # "48", " 5", "6C" → bytes [0x48, 0x3F, 0x6C].
        s = COSString.parse_hex("48 56C")
        assert s.get_bytes() == bytes([0x48, 0x3F, 0x6C])
    finally:
        COSString.FORCE_PARSING = original


def test_parse_hex_rejects_non_hex_character() -> None:
    with pytest.raises(OSError):
        COSString.parse_hex("48GZ")


def test_parse_hex_empty_string_returns_empty() -> None:
    s = COSString.parse_hex("")
    assert s.get_bytes() == b""


# ---------- hex / equality / hash ----------


def test_to_hex_string_uppercase() -> None:
    s = COSString(b"\x00\xff\x10\xab")
    assert s.to_hex_string() == "00FF10AB"


def test_equals_compares_decoded_text_and_hex_flag() -> None:
    a = COSString("hello")
    b = COSString("hello")
    assert a.equals(b)
    c = COSString("hello", force_hex=True)
    assert not a.equals(c)


def test_equals_returns_false_for_non_string() -> None:
    s = COSString("x")
    assert not s.equals(42)
    assert not s.equals("x")


def test_hash_code_changes_with_force_hex_flag() -> None:
    a = COSString(b"hello")
    b = COSString(b"hello", force_hex=True)
    assert a.hash_code() != b.hash_code()


def test_dunder_eq_uses_byte_equality() -> None:
    a = COSString(b"\xfe\xff" + "x".encode("utf-16-be"))
    b = COSString("x")
    # Both decode to ``"x"`` but their bytes differ (UTF-16BE-with-BOM vs
    # PDFDocEncoding); ``__eq__`` compares raw bytes so they are NOT equal.
    assert a != b


def test_dunder_eq_returns_notimplemented_for_other_types() -> None:
    s = COSString("x")
    assert (s == "x") is False
    assert (s == 0) is False


# ---------- force_hex_form flag round-trip ----------


def test_force_hex_form_round_trip() -> None:
    s = COSString(b"abc")
    assert s.is_force_hex_form() is False
    s.set_force_hex_form(True)
    assert s.is_force_hex_form() is True
    assert s.get_force_hex_form() is True


def test_set_value_replaces_raw_bytes() -> None:
    s = COSString(b"old")
    s.set_value(b"new")
    assert s.get_bytes() == b"new"


def test_set_value_copies_input_bytes() -> None:
    """``set_value`` must defensively copy so mutations on the caller's
    buffer do not leak into the COSString."""
    backing = bytearray(b"abc")
    s = COSString(b"")
    s.set_value(backing)
    backing[0] = ord("X")
    assert s.get_bytes() == b"abc"


# ---------- to_string ----------


def test_to_string_renders_inner_text() -> None:
    s = COSString("hello")
    assert s.to_string() == "COSString{hello}"


def test_repr_includes_force_hex_flag() -> None:
    s = COSString(b"x", force_hex=True)
    rendered = repr(s)
    assert "hex=True" in rendered
