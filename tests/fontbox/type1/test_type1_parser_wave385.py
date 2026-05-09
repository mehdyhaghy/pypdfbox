from __future__ import annotations

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_CHARSTRING,
    TOKEN_INTEGER,
    TOKEN_NAME,
    TOKEN_STRING,
    Type1Lexer,
    Type1Parser,
)

_HEADER = b"""
%!PS-AdobeFont-1.0: Wave385 001.000
12 dict begin
/FontName /Wave385 def
/FontType 1 def
/FontMatrix [0.001 0 0 0.001 0 0] readonly def
"""


def _rd(prefix: bytes, plain: bytes, suffix: bytes = b" ND\n") -> bytes:
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=0)
    return prefix + str(len(cipher)).encode("ascii") + b" RD " + cipher + suffix


def test_wave385_lexer_odd_edges_are_tolerant_tokens() -> None:
    lexer = Type1Lexer(b"> 37#10 2#102")

    assert lexer.next_token() == (TOKEN_NAME, ">")
    assert lexer.next_token() == (TOKEN_NAME, "37#10")
    assert lexer.next_token() == (TOKEN_NAME, "2#102")


def test_wave385_lexer_paren_strings_handle_line_continuation_and_unknown_escape() -> None:
    lexer = Type1Lexer("(a\\\r\nb\\q)")

    assert lexer.next_token() == (TOKEN_STRING, "abq")


def test_wave385_lexer_charstring_payload_truncates_at_eof() -> None:
    lexer = Type1Lexer(b"5 RD abc")

    assert lexer.next_token() == (TOKEN_INTEGER, 5)
    assert lexer.next_token() == (TOKEN_CHARSTRING, b"abc")


def test_wave385_lexer_negative_charstring_length_returns_empty_payload() -> None:
    lexer = Type1Lexer(b"-2 RD abc")

    assert lexer.next_token() == (TOKEN_INTEGER, -2)
    assert lexer.next_token() == (TOKEN_CHARSTRING, b"")


def test_wave385_parser_reads_false_font_info_and_negative_encoding_length() -> None:
    header = b"""
%!PS-AdobeFont-1.0: Wave385 001.000
12 dict begin
/FontInfo 2 dict dup begin
  /isFixedPitch false def
  /FullName (Wave 385) readonly def
end readonly def
/FontName /Wave385 def
/Encoding -1 array dup 0 /A put readonly def
"""

    parser = Type1Parser()
    parser.parse(header, Type1FontUtil.eexec_encrypt(b""))

    assert parser.font_dict["FontInfo"]["isFixedPitch"] is False
    assert parser.font_dict["FontInfo"]["FullName"] == "Wave 385"
    assert parser.font_dict["Encoding"] == []


def test_wave385_parser_reads_private_arrays_scalars_and_drains_unknown_values() -> None:
    binary = b"dup /Private 15 dict dup begin\n"
    binary += b"/OtherSubrs [ 1 { pop } 2 { pop pop } ] def\n"
    binary += b"/BlueValues { -10 0 500.5 520 } def\n"
    binary += b"/StdHW [ 70 ] ND\n"
    binary += b"/BlueScale 0.039625 def\n"
    binary += b"/ForceBold false def\n"
    binary += b"/RndStemUp true def\n"
    binary += b"/MinFeature (synthetic) def\n"
    binary += b"/password 5839 def\n"
    binary += b"/lenIV 0 def\n"
    binary += b"/CharStrings 1 dict dup begin\n"
    binary += _rd(b"/A ", b"glyph-a")
    binary += b"end\nend\n"

    parser = Type1Parser()
    parser.parse(_HEADER, Type1FontUtil.eexec_encrypt(binary))

    private = parser.font_dict["Private"]
    assert private["BlueValues"] == [-10, 0, 500.5, 520]
    assert private["StdHW"] == [70]
    assert private["BlueScale"] == 0.039625
    assert private["ForceBold"] is False
    assert private["RndStemUp"] is True
    assert private["MinFeature"] == "synthetic"
    assert private["password"] == 5839
    assert parser.font_dict["CharStrings"] == {"A": b"glyph-a"}


def test_wave385_parser_ignores_binary_blocks_without_private_anchor() -> None:
    parser = Type1Parser()

    parser.parse(_HEADER, Type1FontUtil.eexec_encrypt(b"/CharStrings 0 dict dup begin end"))

    assert parser.font_dict["FontName"] == "Wave385"
    assert "Private" not in parser.font_dict
    assert "CharStrings" not in parser.font_dict
