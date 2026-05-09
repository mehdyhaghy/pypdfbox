"""Wave 394 residual coverage for the Type 1 lexer/parser."""
from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_INTEGER,
    TOKEN_NAME,
    TOKEN_START_ARRAY,
    TOKEN_START_PROC,
    Type1Lexer,
    Type1Parser,
)

_HEADER = b"""
%!PS-AdobeFont-1.0: Wave394 001.000
12 dict begin
/FontInfo 4 dict dup begin
  /FontName /InnerFontInfoName def
  /Unused def
  /Mystery end
/FontName /Wave394 def
/PaintType def
/UnknownTop def
/FontType 1 def
"""


def _rd(prefix: bytes, plain: bytes, suffix: bytes = b" ND\n") -> bytes:
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=0)
    return prefix + str(len(cipher)).encode("ascii") + b" RD " + cipher + suffix


def test_wave394_lexer_remaining_peek_and_trailing_escape_edges() -> None:
    lexer = Type1Lexer("/Name")
    assert lexer.remaining() == "/Name"
    assert lexer.next_token() == ("literal", "Name")
    assert lexer.remaining() == ""
    assert lexer._peek(0) == ""

    assert Type1Lexer("(abc\\").next_token() == ("string", "abc")


def test_wave394_ascii_parser_handles_literal_fontinfo_values_and_empty_defs() -> None:
    parser = Type1Parser()
    parser.parse(_HEADER, Type1FontUtil.eexec_encrypt(b""))

    assert parser.font_dict["FontInfo"] == {"FontName": "InnerFontInfoName"}
    assert parser.font_dict["FontName"] == "Wave394"
    assert parser.font_dict["FontType"] == 1
    assert "PaintType" not in parser.font_dict
    assert "UnknownTop" not in parser.font_dict


def test_wave394_array_proc_and_encoding_readers_handle_eof_and_malformed_entries() -> None:
    parser = Type1Parser()

    proc_lexer = Type1Lexer("{ 1 { 2 } /Name bare")
    assert proc_lexer.next_token()[0] == TOKEN_START_PROC
    assert parser._read_proc(proc_lexer) == [1, [2], "Name", "bare"]

    array_lexer = Type1Lexer("[ [ /A bare 3")
    assert array_lexer.next_token()[0] == TOKEN_START_ARRAY
    assert parser._read_array(array_lexer) == [["A", "bare", 3]]

    assert parser._read_encoding_array(Type1Lexer("dup 3 Name put def"), 4) == [
        ".notdef",
        ".notdef",
        ".notdef",
        ".notdef",
    ]
    assert parser._read_encoding_array(Type1Lexer("dup 1 /A"), 3) == [
        ".notdef",
        "A",
        ".notdef",
    ]
    assert parser._read_encoding_array(Type1Lexer("dup 1 /A noaccess readonly def"), 3) == [
        ".notdef",
        "A",
        ".notdef",
    ]


def test_wave394_private_value_readers_cover_depth_eof_and_operator_synonyms() -> None:
    assert Type1Parser._read_scalar_value(Type1Lexer("[ 1 9")) is None
    assert Type1Parser._read_scalar_value(Type1Lexer("[ 1 ] def")) is None
    assert Type1Parser._read_scalar_value(Type1Lexer("readonly 2 noaccess 3 ND")) == 2
    assert Type1Parser._read_scalar_value(Type1Lexer("4.5 |-")) == 4.5
    assert Type1Parser._read_scalar_value(Type1Lexer("(unterminated")) == "unterminated"

    assert Type1Parser._read_numeric_array_value(Type1Lexer("def")) is None
    assert Type1Parser._read_numeric_array_value(Type1Lexer("")) is None
    assert Type1Parser._read_numeric_array_value(Type1Lexer("[ 1 2")) == [1, 2]
    assert Type1Parser._read_numeric_array_value(Type1Lexer("[ 1 ]")) == [1]

    Type1Parser._drain_value(Type1Lexer("[ { 1 } ] def"))
    Type1Parser._drain_value(Type1Lexer("[ 1"))


def test_wave394_subrs_reader_tolerates_malformed_and_eof_variants() -> None:
    parser = Type1Parser()

    out: list[bytes] = []
    parser._read_subrs(Type1Lexer("array"), out, len_iv=0)
    assert out == []

    out = []
    parser._read_subrs(Type1Lexer("2"), out, len_iv=0)
    assert out == [b"", b""]

    out = []
    parser._read_subrs(Type1Lexer("1 array dup"), out, len_iv=0)
    assert out == [b""]

    out = []
    parser._read_subrs(Type1Lexer("1 array dup 0"), out, len_iv=0)
    assert out == [b""]

    out = []
    parser._read_subrs(Type1Lexer("1 array dup 0 3 abc"), out, len_iv=0)
    assert out == [b""]

    out = []
    parser._read_subrs(Type1Lexer(_rd(b"1 array dup 0 ", b"body", suffix=b"")), out, 0)
    assert out == [b"body"]

    out = []
    parser._read_subrs(Type1Lexer(b"1 array dup 0 3 RD abc NP"), out, len_iv=4)
    assert out == [b""]

    two_entries = _rd(b"2 array dup 0 ", b"zero", suffix=b" ")
    two_entries += _rd(b"dup 1 ", b"one", suffix=b" NP\n")
    out = []
    parser._read_subrs(Type1Lexer(two_entries), out, len_iv=0)
    assert out == [b"zero", b"one"]


def test_wave394_charstrings_reader_skips_malformed_entries_and_eof_variants() -> None:
    parser = Type1Parser()

    out: dict[str, bytes] = {}
    parser._read_charstrings(Type1Lexer(""), out, len_iv=0)
    assert out == {}

    parser._read_charstrings(Type1Lexer("1 dict"), out, len_iv=0)
    assert out == {}

    parser._read_charstrings(Type1Lexer("1 dict dup begin junk /A Name /B"), out, 0)
    assert out == {}

    parser._read_charstrings(Type1Lexer(b"1 dict dup begin /A 3 abc end"), out, 0)
    assert out == {}

    parser._read_charstrings(Type1Lexer(_rd(b"1 dict dup begin /A ", b"glyph", b"")), out, 0)
    assert out == {"A": b"glyph"}

    out = {}
    parser._read_charstrings(
        Type1Lexer(_rd(b"1 dict dup begin /A ", b"glyph", b" /Next")),
        out,
        0,
    )
    assert out == {"A": b"glyph"}


def test_wave394_binary_parser_private_and_charstring_residual_paths() -> None:
    binary = b"dup /Private 10 dict dup begin\n"
    binary += b"/BlueValues def\n"
    binary += b"/OtherBlues [ -20 0 ] def\n"
    binary += b"/lenIV 0 def\n"
    binary += b"/Subrs 2 array\n"
    binary += _rd(b"dup 5 ", b"ignored-out-of-range", b" put\n")
    binary += b"/CharStrings 2 dict dup begin\n"
    binary += b"readonly\n"
    binary += b"/BadLen Name\n"
    binary += _rd(b"/A ", b"glyph-a", b" readonly noaccess def\n")
    binary += b"end\nend\n"

    parser = Type1Parser()
    parser.parse(_HEADER, Type1FontUtil.eexec_encrypt(binary))

    private = parser.font_dict["Private"]
    assert private["OtherBlues"] == [-20, 0]
    assert private["lenIV"] == 0
    assert private["Subrs"] == [b"", b""]
    assert parser.font_dict["CharStrings"] == {"A": b"glyph-a"}


def test_wave394_coerce_value_name_and_fallback_paths() -> None:
    lexer = Type1Lexer("")
    assert Type1Parser._coerce_value(TOKEN_NAME, "true", lexer) is True
    assert Type1Parser._coerce_value(TOKEN_NAME, "false", lexer) is False
    assert Type1Parser._coerce_value(TOKEN_NAME, "OtherName", lexer) == "OtherName"

    opaque: Any = object()
    assert Type1Parser._coerce_value("opaque", opaque, lexer) is opaque
    assert Type1Parser._coerce_value(TOKEN_INTEGER, 3, lexer) == 3
