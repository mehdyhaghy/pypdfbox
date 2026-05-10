"""Ported upstream tests for ``Type1Parser``.

Upstream PDFBox ships no dedicated ``Type1ParserTest.java`` — coverage of
``Type1Parser`` is exercised indirectly through ``Type1FontUtilTest`` and
through end-to-end PDF rendering tests. This file therefore mirrors
those upstream behaviours that *do* directly exercise ``Type1Parser``'s
public methods, translated to pytest:

- ``Type1FontUtilTest.testHexEncoding`` round-trips eexec ciphertext
  through the parser's ``hex_to_binary`` and ``decrypt`` (Type1Parser
  static helpers, mirrored from Type1Parser.java lines 927 / 978).
- The "valid PFA header is parseable end-to-end" round-trip is what
  PDFBox's font-rendering integration tests assert on every fixture;
  we reproduce a synthetic minimal version here.

When upstream eventually adds a ``Type1ParserTest`` we should re-port
the cases here and keep filenames upstream-identical for diffability.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import Type1Parser


# Mirrors the structure of Type1FontUtilTest.testHexEncoding —
# round-tripping a payload through ``hex_to_binary`` should be the
# inverse of upper-hex encoding.
def test_hex_to_binary_round_trip() -> None:
    payload = bytes(range(256))
    hex_text = payload.hex().upper().encode("ascii")
    assert Type1Parser.hex_to_binary(hex_text) == payload


def test_hex_to_binary_drops_unmatched_trailing_nibble() -> None:
    # Upstream truncates via integer division: ``new byte[len / 2]``.
    assert Type1Parser.hex_to_binary(b"414") == b"A"


def test_is_binary_recognises_raw_eexec() -> None:
    # First byte 0xFF is not a hex digit and not whitespace → raw.
    assert Type1Parser.is_binary(b"\xffhex")


def test_is_binary_recognises_ascii_hex() -> None:
    assert not Type1Parser.is_binary(b"414243")
    assert not Type1Parser.is_binary(b"41 42")


def test_decrypt_no_encryption_passthrough() -> None:
    # lenIV of -1 means "no encryption" (undocumented PDFBox tolerance).
    assert Type1Parser.decrypt(b"abcdef", Type1Parser.EEXEC_KEY, -1) == b"abcdef"


def test_decrypt_handles_empty_and_short_input() -> None:
    assert Type1Parser.decrypt(b"", Type1Parser.EEXEC_KEY, 4) == b""
    # n > len(cipher): upstream returns an empty array.
    assert Type1Parser.decrypt(b"ab", Type1Parser.EEXEC_KEY, 4) == b""


def test_parse_ascii_rejects_empty() -> None:
    parser = Type1Parser()
    with pytest.raises(OSError, match="empty"):
        parser.parse_ascii(b"")


def test_parse_ascii_rejects_non_postscript_header() -> None:
    parser = Type1Parser()
    with pytest.raises(OSError, match="Invalid start"):
        parser.parse_ascii(b"\x00\x00garbage")


def test_parse_binary_round_trip() -> None:
    """End-to-end: hand-craft a Private + CharStrings PostScript body,
    eexec-encrypt it, parse_binary, and verify decoded glyph payload.

    With ``lenIV = 0`` the charstring cipher consumes no warm-up bytes;
    we still have to encrypt the desired plaintext glyph once because
    the parser unconditionally runs ``decrypt`` on the captured payload.
    """
    glyph_plain = b"World"
    glyph_cipher = Type1FontUtil.charstring_encrypt(glyph_plain, len_iv=0)
    plain = (
        b"dup /Private 4 dict dup begin\n"
        b"/lenIV 0 def\n"
        b"/BlueValues [ -20 0 800 820 ] def\n"
        b"2 index\n"
        b"/CharStrings 1 dict dup begin\n"
        b"/Hello " + str(len(glyph_cipher)).encode() + b" RD " + glyph_cipher + b" ND\n"
        b"end\n"
    )
    cipher = Type1FontUtil.eexec_encrypt(plain)

    parser = Type1Parser()
    parser.parse_binary(cipher)

    assert parser.font_dict["CharStrings"]["Hello"] == glyph_plain
    assert parser.font_dict["Private"]["BlueValues"] == [-20, 0, 800, 820]
    assert parser.font_dict["Private"]["lenIV"] == 0
