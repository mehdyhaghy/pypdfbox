"""Ported upstream tests for ``Hex``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/util/TestHexUtil.java``
(PDFBox 3.0.x). Mirrors the four hand-written upstream test methods over
the entire 256-byte range plus a couple of UTF-16BE / short-to-chars
corner cases.
"""

from __future__ import annotations

from pypdfbox.util import Hex


def test_get_chars_from_short_without_passing_in_a_buffer() -> None:
    assert Hex.get_chars(0x0000) == "0000"
    assert Hex.get_chars(0x000F) == "000F"
    assert Hex.get_chars(0xABCD) == "ABCD"
    # Upstream uses a 32-bit value 0xCAFEBABE — Hex.getChars((short) ...) only
    # keeps the low 16 bits, so the expected output is "BABE".
    assert Hex.get_chars(0xCAFEBABE) == "BABE"


def test_get_chars_utf16be() -> None:
    assert Hex.get_chars_utf16_be("ab") == "00610062"
    assert Hex.get_chars_utf16_be("帮助") == "5E2E52A9"


def test_misc_get_bytes_get_string_decode_hex() -> None:
    """Cover the full byte range with ``get_bytes`` / ``get_string`` /
    ``decode_hex`` (upstream ``testMisc``)."""
    byte_src = bytearray(range(256))
    for i in range(256):
        single = Hex.get_bytes(i)
        assert len(single) == 2
        # Upstream uses ``String.format("%02X", i)``.
        expected = f"{i:02X}".encode("ascii")
        assert single == expected
        text = Hex.get_string(i)
        assert text.encode("ascii") == expected

        assert Hex.decode_hex(text) == bytes([i])

    byte_dst = Hex.get_bytes(bytes(byte_src))
    assert len(byte_dst) == len(byte_src) * 2

    dst_string = Hex.get_string(bytes(byte_src))
    assert len(dst_string) == len(byte_src) * 2

    assert dst_string.encode("ascii") == byte_dst
    assert Hex.decode_hex(dst_string) == bytes(byte_src)


def test_get_hex_value() -> None:
    valid_hex_characters: set[str] = set()
    for c in "0123456789":
        valid_hex_characters.add(c)
        assert Hex.get_hex_value(c) == int(c, 16)
    for c in "abcdef":
        valid_hex_characters.add(c)
        assert Hex.get_hex_value(c) == int(c, 16)
    for c in "ABCDEF":
        valid_hex_characters.add(c)
        assert Hex.get_hex_value(c) == int(c, 16)
    assert len(valid_hex_characters) == 22
    for code_point in range(256):
        ch = chr(code_point)
        if ch not in valid_hex_characters:
            assert Hex.get_hex_value(ch) == -256
