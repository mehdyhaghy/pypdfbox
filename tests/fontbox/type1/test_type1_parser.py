"""Tests for the cleartext-header parser and lexer.

We use synthetic PostScript snippets that follow the real PFA shape but
trim everything ``Type1Font``'s accessors do not consult — the parser
should pick out the well-known top-level keys and the FontInfo dict
contents without choking on intervening operators.
"""

from __future__ import annotations

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_END_ARRAY,
    TOKEN_END_DICT,
    TOKEN_END_PROC,
    TOKEN_INTEGER,
    TOKEN_LITERAL,
    TOKEN_NAME,
    TOKEN_REAL,
    TOKEN_START_ARRAY,
    TOKEN_START_DICT,
    TOKEN_START_PROC,
    TOKEN_STRING,
    Type1Lexer,
    Type1Parser,
)


# ---------- Type1Lexer ----------


def _tokens(src: str) -> list[tuple[str, object]]:
    lex = Type1Lexer(src)
    out: list[tuple[str, object]] = []
    while True:
        tok = lex.next_token()
        if tok is None:
            break
        out.append(tok)
    return out


def test_lexer_skips_whitespace_between_tokens() -> None:
    toks = _tokens("  /Foo   42   def  ")
    assert toks == [
        (TOKEN_LITERAL, "Foo"),
        (TOKEN_INTEGER, 42),
        (TOKEN_NAME, "def"),
    ]


def test_lexer_handles_line_comments() -> None:
    src = "/Foo % this is a comment\n 42 def"
    assert _tokens(src) == [
        (TOKEN_LITERAL, "Foo"),
        (TOKEN_INTEGER, 42),
        (TOKEN_NAME, "def"),
    ]


def test_lexer_recognises_real_numbers() -> None:
    toks = _tokens("0.001 -1.5 2e3")
    assert toks[0][0] == TOKEN_REAL and toks[0][1] == 0.001
    assert toks[1][0] == TOKEN_REAL and toks[1][1] == -1.5
    # 2e3 is a real (scientific notation).
    assert toks[2][0] == TOKEN_REAL and toks[2][1] == 2000.0


def test_lexer_recognises_radix_integers() -> None:
    toks = _tokens("16#FF 2#1010")
    assert toks == [(TOKEN_INTEGER, 255), (TOKEN_INTEGER, 10)]


def test_lexer_paren_string_with_escapes() -> None:
    toks = _tokens(r"(hello\nworld)")
    assert toks == [(TOKEN_STRING, "hello\nworld")]


def test_lexer_paren_string_nested_balanced() -> None:
    toks = _tokens("(outer (inner) tail)")
    assert toks == [(TOKEN_STRING, "outer (inner) tail")]


def test_lexer_paren_string_octal_escape() -> None:
    toks = _tokens(r"(\101)")  # octal 101 = 'A'
    assert toks == [(TOKEN_STRING, "A")]


def test_lexer_hex_string() -> None:
    toks = _tokens("<48656C6C6F>")
    assert toks == [(TOKEN_STRING, b"Hello")]


def test_lexer_hex_string_with_whitespace_and_odd_length() -> None:
    toks = _tokens("<48 65 6c 6c 6>")  # last "6" auto-padded to "60"
    assert toks == [(TOKEN_STRING, b"Hell\x60")]


def test_lexer_array_and_proc_delimiters() -> None:
    toks = _tokens("[ 1 2 ] { add }")
    assert toks == [
        (TOKEN_START_ARRAY, "["),
        (TOKEN_INTEGER, 1),
        (TOKEN_INTEGER, 2),
        (TOKEN_END_ARRAY, "]"),
        (TOKEN_START_PROC, "{"),
        (TOKEN_NAME, "add"),
        (TOKEN_END_PROC, "}"),
    ]


def test_lexer_dict_delimiters() -> None:
    toks = _tokens("<< /Key 1 >>")
    assert toks[0] == (TOKEN_START_DICT, "<<")
    assert toks[-1] == (TOKEN_END_DICT, ">>")


def test_lexer_peek_does_not_consume() -> None:
    lex = Type1Lexer("/Foo 1 def")
    assert lex.peek_token() == (TOKEN_LITERAL, "Foo")
    assert lex.peek_token() == (TOKEN_LITERAL, "Foo")
    assert lex.next_token() == (TOKEN_LITERAL, "Foo")
    assert lex.next_token() == (TOKEN_INTEGER, 1)


def test_lexer_eof_returns_none() -> None:
    lex = Type1Lexer("")
    assert lex.next_token() is None
    assert lex.peek_token() is None


def test_lexer_accepts_bytes_input() -> None:
    toks = _tokens("/A 1 def".encode("latin-1"))  # type: ignore[arg-type]
    # Above used encode for clarity but lexer accepts bytes.
    lex = Type1Lexer(b"/A 1 def")
    out: list[tuple[str, object]] = []
    while True:
        tok = lex.next_token()
        if tok is None:
            break
        out.append(tok)
    assert out == toks


# ---------- Type1Parser.parse ----------


_SAMPLE_HEADER = """
%!PS-AdobeFont-1.0: TestFont 001.000
12 dict begin
/FontInfo 7 dict dup begin
  /version (001.000) readonly def
  /Notice (Sample notice) readonly def
  /FullName (Test Font Regular) readonly def
  /FamilyName (TestFont) readonly def
  /Weight (Bold) readonly def
  /ItalicAngle -12 def
  /isFixedPitch true def
end readonly def
/FontName /TestFont def
/PaintType 0 def
/FontType 1 def
/FontMatrix [ 0.001 0 0 0.001 0 0 ] readonly def
/Encoding StandardEncoding def
/FontBBox { -50 -200 1000 800 } readonly def
/UniqueID 12345 def
"""


def test_parser_extracts_top_level_keys() -> None:
    # Use a real round-trippable eexec block so the binary half also
    # exercises decryption.
    plain_private = b"dup /Private 5 dict dup begin /lenIV 4 def\n"
    cipher = Type1FontUtil.eexec_encrypt(plain_private)

    parser = Type1Parser()
    parser.parse(_SAMPLE_HEADER.encode("latin-1"), cipher)

    fd = parser.font_dict
    assert fd["FontName"] == "TestFont"
    assert fd["FontType"] == 1
    assert fd["PaintType"] == 0
    assert fd["UniqueID"] == 12345
    assert fd["Encoding"] == "StandardEncoding"


def test_parser_extracts_font_matrix_array() -> None:
    parser = Type1Parser()
    parser.parse(_SAMPLE_HEADER.encode("latin-1"), Type1FontUtil.eexec_encrypt(b""))
    matrix = parser.font_dict["FontMatrix"]
    assert matrix == [0.001, 0, 0, 0.001, 0, 0]


def test_parser_extracts_font_info_dict() -> None:
    parser = Type1Parser()
    parser.parse(_SAMPLE_HEADER.encode("latin-1"), Type1FontUtil.eexec_encrypt(b""))
    info = parser.font_dict["FontInfo"]
    assert info["FullName"] == "Test Font Regular"
    assert info["FamilyName"] == "TestFont"
    assert info["Weight"] == "Bold"
    assert info["ItalicAngle"] == -12
    assert info["isFixedPitch"] is True
    assert info["Notice"] == "Sample notice"


def test_parser_decrypts_binary_segment() -> None:
    plain = b"this is the eexec body"
    cipher = Type1FontUtil.eexec_encrypt(plain)
    parser = Type1Parser()
    parser.parse(b"%!PS\n/FontName /A def\n", cipher)
    assert parser.decrypted_binary == plain


def test_parser_round_trip_through_font() -> None:
    """``Type1Font.create_with_segments`` should expose all the metadata
    the parser harvested via the same accessor surface as ``from_bytes``."""
    from pypdfbox.fontbox.type1.type1_font import Type1Font

    cipher = Type1FontUtil.eexec_encrypt(b"private body")
    font = Type1Font.create_with_segments(_SAMPLE_HEADER.encode("latin-1"), cipher)
    assert font.get_name() == "TestFont"
    assert font.get_full_name() == "Test Font Regular"
    assert font.get_family_name() == "TestFont"
    assert font.get_weight() == "Bold"
    assert font.get_italic_angle() == -12.0
    assert font.is_italic() is True
    assert font.get_is_fixed_pitch() is True
    assert font.is_fixed_pitch() is True
    assert font.get_notice() == "Sample notice"
    assert font.font_matrix == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert font.units_per_em == 1000
    assert font.decrypted_binary == b"private body"


def test_parser_handles_missing_font_info() -> None:
    src = b"%!PS\n/FontName /A def\n"
    parser = Type1Parser()
    parser.parse(src, Type1FontUtil.eexec_encrypt(b""))
    assert parser.font_dict["FontName"] == "A"
    assert "FontInfo" not in parser.font_dict
