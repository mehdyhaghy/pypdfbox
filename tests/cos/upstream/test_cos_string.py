"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSString.java

Upstream extends TestCOSBase. Tests that depend on ``COSWriter`` to verify
the PDF-encoded form are translated through pypdfbox's ``COSWriter``
string helpers.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSString
from pypdfbox.pdfwriter.cos_writer import COSWriter


def _create_hex(s: str) -> str:
    """Mirrors upstream ``createHex`` (chars ↦ uppercase hex of code point)."""
    return "".join(format(ord(c), "X") for c in s)


def test_set_force_hex_literal_form() -> None:
    # Upstream verifies the bytes COSWriter emits — pypdfbox has no writer
    # yet. We assert the flag round-trips and the in-memory state matches.
    cos_str = COSString("Test with a text and a few numbers 1, 2 and 3")
    assert not cos_str.is_force_hex_form()
    cos_str.set_force_hex_form(True)
    assert cos_str.is_force_hex_form()
    cos_str.set_force_hex_form(False)
    assert not cos_str.is_force_hex_form()


def test_from_hex() -> None:
    expected = "Quick and simple test"
    hex_form = _create_hex(expected)
    test1 = COSString.parse_hex(hex_form)
    assert test1.get_string() == expected
    # Invalid hex characters trigger an OSError (mirrors PDFBox IOException).
    with pytest.raises(OSError):
        COSString.parse_hex(hex_form + "xx")


def test_get_hex() -> None:
    expected = "Test subject for testing getHex"
    test1 = COSString(expected)
    hex_form = _create_hex(expected)
    assert test1.to_hex_string() == hex_form

    esc_char_string = "( test#some) escaped< \\chars>!~1239857 "
    esc_cs = COSString(esc_char_string)
    assert esc_cs.to_hex_string() == _create_hex(esc_char_string)


def test_get_string() -> None:
    test_str = "Test subject for getString()"
    test1 = COSString(test_str)
    assert test1.get_string() == test_str

    hex_str = COSString.parse_hex(_create_hex(test_str))
    assert hex_str.get_string() == test_str

    esc_char_string = "( test#some) escaped< \\chars>!~1239857 "
    escaped_string = COSString(esc_char_string)
    assert escaped_string.get_string() == esc_char_string

    test_str = "Line1\nLine2\nLine3\n"
    line_feed_string = COSString(test_str)
    assert line_feed_string.get_string() == test_str


def test_get_bytes() -> None:
    esc_char_string = "( test#some) escaped< \\chars>!~1239857 "
    s = COSString(esc_char_string)
    assert s.get_bytes() == esc_char_string.encode("latin-1")


def test_write_pdf() -> None:
    out = io.BytesIO()
    COSWriter.write_string(COSString("Test"), out)
    assert out.getvalue() == b"(Test)"

    out = io.BytesIO()
    COSWriter.write_string(COSString(r"( test#some) escaped< \chars>!~1239857 "), out)
    assert out.getvalue() == br"(\( test#some\) escaped< \\chars>!~1239857 )"

    cos_str = COSString("Test")
    cos_str.set_force_hex_form(True)
    out = io.BytesIO()
    COSWriter.write_string(cos_str, out)
    assert out.getvalue() == b"<54657374>"


def test_unicode() -> None:
    expected = "洪水"
    out = io.BytesIO()

    COSWriter.write_string(COSString(expected), out)

    data = out.getvalue()
    assert data == b"<FEFF6D2A6C34>"
    assert COSString.parse_hex(data[1:-1].decode("ascii")).get_string() == expected


def test_accept() -> None:
    out = io.BytesIO()

    COSString("Test").accept(COSWriter(out))

    assert out.getvalue() == b"(Test)"


def test_equals() -> None:
    # Several rounds for consistency.
    for _ in range(10):
        # Reflexive
        x1 = COSString("Test")
        assert x1 == x1

        # Symmetric.
        y1 = COSString("Test")
        assert x1 == y1
        assert y1 == x1
        x2 = COSString("Test")
        x2.set_force_hex_form(True)
        # x1 != x2 (different hex flag) ⇒ x2 != x1.
        assert x1 != x2
        assert x2 != x1

        # Transitive.
        z1 = COSString("Test")
        assert x1 == y1
        assert y1 == z1
        assert x1 == z1
        # Negative consequence: x1 == y1 && y1 != x2 ⇒ x1 != x2.
        assert x1 == y1
        assert y1 != x2
        assert x1 != x2


def test_hash_code() -> None:
    str1 = COSString("Test1")
    str2 = COSString("Test2")
    assert hash(str1) != hash(str2)
    str3 = COSString("Test1")
    assert hash(str1) == hash(str3)
    str3.set_force_hex_form(True)
    assert hash(str1) != hash(str3)


def test_compare_from_hex_string() -> None:
    # PDFBOX-2401
    test1 = COSString.parse_hex("000000FF000000")
    test2 = COSString.parse_hex("000000FF00FFFF")
    assert test1 == test1
    assert test2 == test2
    assert test1.to_hex_string() != test2.to_hex_string()
    assert test1.get_bytes() != test2.get_bytes()
    assert test1 != test2
    assert test2 != test1
    assert test1.get_string() != test2.get_string()


def test_empty_string_with_bom() -> None:
    # PDFBOX-3881: a hex string consisting only of the BOM is empty.
    assert COSString.parse_hex("FEFF").get_string() == ""
    assert COSString.parse_hex("FFFE").get_string() == ""


def test_is_set_direct() -> None:
    s = COSString("test cos string")
    s.set_direct(True)
    assert s.is_direct()
    s.set_direct(False)
    assert not s.is_direct()


def test_set_value_replaces_payload() -> None:
    # Upstream ``COSString.setValue(byte[])`` — deprecated but still
    # part of the published API in 3.0; mirrored 1:1.
    s = COSString(b"old")
    s.set_value(b"new")
    assert s.get_bytes() == b"new"


def test_constructor_force_hex_overload() -> None:
    # Mirrors ``COSString(byte[], boolean)`` and
    # ``COSString(String, boolean)`` constructors — set the hex flag at
    # construction time without the post-init ``setForceHexForm`` call.
    s_bytes = COSString(b"abc", force_hex=True)
    assert s_bytes.is_force_hex_form()
    s_str = COSString("abc", force_hex=True)
    assert s_str.is_force_hex_form()


def test_force_parsing_recovers_malformed_hex() -> None:
    # Mirrors upstream ``FORCE_PARSING`` system-property branch in
    # ``parseHex`` (lines 165-169 + 182-186 of COSString.java) — each
    # malformed pair becomes ``?`` (0x3F) and a warning is logged.
    saved = COSString.FORCE_PARSING
    COSString.FORCE_PARSING = True
    try:
        # 'H' (0x48) + malformed pair "ZZ" + 'o' (0x6F).
        s = COSString.parse_hex("48ZZ6F")
        assert s.get_bytes() == b"H?o"
    finally:
        COSString.FORCE_PARSING = saved
