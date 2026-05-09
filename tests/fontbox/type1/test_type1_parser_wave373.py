from __future__ import annotations

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_CHARSTRING,
    TOKEN_NAME,
    Type1Lexer,
    Type1Parser,
)


_HEADER = b"""
%!PS-AdobeFont-1.0: Wave373 001.000
12 dict begin
/FontName /Wave373 def
/FontType 1 def
/FontMatrix [0.001 0 0 0.001 0 0] readonly def
"""


def _rd_entry(prefix: bytes, operator: bytes, plain: bytes, suffix: bytes) -> bytes:
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=0)
    return prefix + str(len(cipher)).encode("ascii") + b" " + operator + b" " + cipher + suffix


def test_wave373_normalise_eexec_keeps_short_and_binary_segments() -> None:
    assert Type1Parser._normalise_eexec_segment(b"ABC") == b"ABC"
    assert Type1Parser._normalise_eexec_segment(b"\x80ABCDEF") == b"\x80ABCDEF"


def test_wave373_normalise_eexec_truncates_odd_ascii_hex_nibble() -> None:
    assert Type1Parser._normalise_eexec_segment(b"41 42 4") == b"AB"


def test_wave373_lexer_recognises_dash_bar_charstring_operator() -> None:
    lexer = Type1Lexer(b"/A 3 -| xyz ND")

    assert lexer.next_token() == ("literal", "A")
    assert lexer.next_token() == ("integer", 3)
    assert lexer.next_token() == (TOKEN_CHARSTRING, b"xyz")


def test_wave373_lexer_treats_dash_bar_without_integer_as_name() -> None:
    lexer = Type1Lexer(b"-|")

    assert lexer.next_token() == (TOKEN_NAME, "-|")


def test_wave373_parser_reads_out_of_order_subrs_and_leniv_zero_charstrings() -> None:
    binary = b"dup /Private 9 dict dup begin\n/lenIV 0 def\n/Subrs 3 array\n"
    binary += _rd_entry(b"dup 2 ", b"RD", b"subr-two", b" NP\n")
    binary += _rd_entry(b"dup 0 ", b"-|", b"subr-zero", b" |\n")
    binary += b"def\n/CharStrings 2 dict dup begin\n"
    binary += _rd_entry(b"/.notdef ", b"RD", b"notdef-body", b" ND\n")
    binary += _rd_entry(b"/A ", b"-|", b"glyph-a-body", b" |-\n")
    binary += b"end\nend\n"

    parser = Type1Parser()
    parser.parse(_HEADER, Type1FontUtil.eexec_encrypt(binary))

    assert parser.font_dict["Private"]["lenIV"] == 0
    assert parser.font_dict["Private"]["Subrs"] == [b"subr-zero", b"", b"subr-two"]
    assert parser.font_dict["CharStrings"] == {
        ".notdef": b"notdef-body",
        "A": b"glyph-a-body",
    }


def test_wave373_parser_stores_empty_bytes_for_bad_charstring_ciphertext() -> None:
    binary = (
        b"dup /Private 2 dict dup begin\n"
        b"/CharStrings 1 dict dup begin\n"
        b"/A 3 RD abc ND\n"
        b"end\nend\n"
    )

    parser = Type1Parser()
    parser.parse(_HEADER, Type1FontUtil.eexec_encrypt(binary))

    assert parser.font_dict["CharStrings"]["A"] == b""


def test_wave373_parse_tolerates_binary_tokenisation_failure() -> None:
    parser = Type1Parser()

    parsed = parser.parse(
        _HEADER,
        Type1FontUtil.eexec_encrypt(b"dup /Private 1 dict dup begin <Z>"),
    )

    assert parsed["FontName"] == "Wave373"
    assert "Private" not in parsed
