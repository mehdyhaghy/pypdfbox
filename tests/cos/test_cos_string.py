from __future__ import annotations

import pytest

from pypdfbox.cos import COSString


def test_construct_from_bytes() -> None:
    s = COSString(b"hello")
    assert s.get_bytes() == b"hello"
    assert not s.is_force_hex_form()


def test_construct_from_str_uses_latin1() -> None:
    s = COSString("hello")
    assert s.get_bytes() == b"hello"


def test_construct_with_force_hex_flag() -> None:
    # Mirrors upstream ``COSString(byte[], boolean)`` /
    # ``COSString(String, boolean)`` constructors — flag set at
    # construction time, no need to flip it afterwards.
    s = COSString(b"hello", force_hex=True)
    assert s.is_force_hex_form()
    s2 = COSString("hello", force_hex=True)
    assert s2.is_force_hex_form()


def test_force_hex_form_flag() -> None:
    s = COSString(b"\x01\x02")
    s.set_force_hex_form(True)
    assert s.is_force_hex_form()


def test_set_value_replaces_bytes() -> None:
    # Mirrors upstream ``COSString.setValue(byte[])`` (deprecated).
    s = COSString(b"old")
    s.set_value(b"new")
    assert s.get_bytes() == b"new"


def test_set_value_copies_input() -> None:
    # Upstream ``setValue`` does ``Arrays.copyOf(value, value.length)`` —
    # mutating the caller's buffer afterwards must not leak through.
    buf = bytearray(b"abc")
    s = COSString(b"x")
    s.set_value(buf)
    buf[0] = 0x7A  # 'z'
    assert s.get_bytes() == b"abc"


def test_pdfbox_camelcase_aliases() -> None:
    s = COSString(b"hello")
    assert s.getBytes() == b"hello"
    assert s.getString() == "hello"
    assert s.isForceHexForm() is False

    s.setForceHexForm(True)

    assert s.is_force_hex_form() is True
    assert s.toHexString() == "68656C6C6F".upper()


def test_parse_hex_basic() -> None:
    s = COSString.parse_hex("48656C6C6F")
    assert s.get_bytes() == b"Hello"
    # Upstream ``parseHex`` returns a string in the *default* (literal)
    # form — not hex-form — so writers can re-emit it as ``(...)``.
    assert not s.is_force_hex_form()


def test_parse_hex_strips_leading_and_trailing_whitespace_only() -> None:
    # Upstream skips only leading/trailing whitespace (lines 138-148 of
    # COSString.java); internal whitespace would feed Hex.getHexValue
    # which returns -1, raising IOException.
    s = COSString.parse_hex("  48656C6C6F\n")
    assert s.get_bytes() == b"Hello"


def test_parse_hex_internal_whitespace_raises() -> None:
    # Mirrors strict upstream behaviour — internal whitespace is invalid.
    with pytest.raises(OSError):
        COSString.parse_hex("48 65 6C 6C 6F")


def test_parse_hex_pads_odd_digits() -> None:
    # Per ISO 32000-1 §7.3.4.3 — trailing odd digit gets a "0".
    s = COSString.parse_hex("4")
    assert s.get_bytes() == b"\x40"


def test_parse_hex_invalid_raises() -> None:
    # parse_hex raises OSError to mirror PDFBox's IOException contract
    # (translated to OSError in pypdfbox per the test-porting conventions).
    with pytest.raises(OSError):
        COSString.parse_hex("zz")


def test_parse_hex_force_parsing_substitutes_question_mark() -> None:
    # Toggling FORCE_PARSING (mirrors upstream's static system property)
    # makes malformed pairs decode to '?' (0x3F) rather than raising.
    saved = COSString.FORCE_PARSING
    COSString.FORCE_PARSING = True
    try:
        s = COSString.parse_hex("48ZZ6F")  # 'H', '?', 'o'
        assert s.get_bytes() == b"H?o"
    finally:
        COSString.FORCE_PARSING = saved


def test_get_string_utf16_be_bom() -> None:
    raw = b"\xfe\xff" + "Héllo".encode("utf-16-be")
    assert COSString(raw).get_string() == "Héllo"


def test_get_string_utf16_le_bom() -> None:
    raw = b"\xff\xfe" + "Héllo".encode("utf-16-le")
    assert COSString(raw).get_string() == "Héllo"


def test_get_string_utf8_bom_pdf_2_0() -> None:
    raw = b"\xef\xbb\xbf" + "naïve".encode("utf-8")
    assert COSString(raw).get_string() == "naïve"


def test_get_string_default_pdfdocencoding_fallback() -> None:
    # No BOM → latin-1 (approximation of PDFDocEncoding).
    assert COSString(b"plain").get_string() == "plain"


def test_equality_includes_hex_flag() -> None:
    a = COSString(b"abc")
    b = COSString(b"abc")
    assert a == b
    b.set_force_hex_form(True)
    assert a != b


def test_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    s = COSString(b"x")
    s.accept(v)
    assert v.calls == [("string", s)]


def test_equals_method_mirrors_upstream() -> None:
    # Upstream ``equals`` compares the *decoded* text and the hex flag —
    # two COSStrings whose payloads decode to the same Unicode text are
    # equal regardless of underlying encoding (PDFDocEncoding vs UTF-16BE
    # BOM, for instance).
    a = COSString("Hello")
    b = COSString("Hello")
    assert a.equals(b)
    assert not a.equals(COSString("Hello", force_hex=True))
    assert not a.equals("Hello")  # non-COSString
    assert not a.equals(None)


def test_hash_code_method_mirrors_upstream() -> None:
    # Upstream ``hashCode`` = Arrays.hashCode(bytes) + (forceHexForm ? 17 : 0).
    s1 = COSString("Test1")
    s2 = COSString("Test1")
    assert s1.hash_code() == s2.hash_code()
    s3 = COSString("Test1", force_hex=True)
    assert s1.hash_code() != s3.hash_code()
    assert s3.hash_code() - s1.hash_code() == 17


def test_to_string_method_mirrors_upstream() -> None:
    # Upstream ``toString`` returns ``"COSString{<decoded>}"``.
    assert COSString("hello").to_string() == "COSString{hello}"
    assert COSString(b"abc").to_string() == "COSString{abc}"
