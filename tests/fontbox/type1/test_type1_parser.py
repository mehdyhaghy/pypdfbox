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


# ---------- public parity helpers (parse_ascii / parse_binary / ...) ----------


def test_parse_ascii_rejects_empty_segment() -> None:
    import pytest

    parser = Type1Parser()
    with pytest.raises(OSError, match="empty"):
        parser.parse_ascii(b"")


def test_parse_ascii_rejects_invalid_header() -> None:
    import pytest

    parser = Type1Parser()
    with pytest.raises(OSError, match="Invalid start"):
        parser.parse_ascii(b"XXnot postscript")


def test_parse_ascii_walks_full_dict() -> None:
    """``parse_ascii`` should populate the same top-level keys as the
    streaming ``parse`` path when fed a well-formed cleartext segment."""
    src = (
        b"%!PS-AdobeFont-1.0: ParseAsciiFont 001.000\n"
        b"12 dict begin\n"
        b"/FontInfo 1 dict dup begin\n"
        b"  /FullName (Parse Ascii Font) readonly def\n"
        b"end readonly def\n"
        b"/FontName /ParseAsciiFont def\n"
        b"/PaintType 0 def\n"
        b"/FontType 1 def\n"
        b"/FontMatrix [ 0.001 0 0 0.001 0 0 ] readonly def\n"
        b"/Encoding StandardEncoding def\n"
        b"/FontBBox { -50 -200 1000 800 } readonly def\n"
        b"/UniqueID 99 def\n"
        b"currentdict end\n"
        b"currentfile eexec\n"
    )
    parser = Type1Parser()
    parser.parse_ascii(src)

    assert parser.font_dict["FontName"] == "ParseAsciiFont"
    assert parser.font_dict["FontType"] == 1
    assert parser.font_dict["UniqueID"] == 99
    assert parser.font_dict["Encoding"] == "StandardEncoding"
    assert parser.font_dict["FontInfo"]["FullName"] == "Parse Ascii Font"


def test_parse_binary_round_trips_through_eexec() -> None:
    """``parse_binary`` should detect raw eexec, decrypt it, and harvest
    Private/Subrs/CharStrings just like the streaming ``parse``."""
    # Charstring payload must already be encrypted in the source bytes
    # because ``parse_binary`` re-applies the charstring cipher on its way
    # out. With ``lenIV = 0`` the cipher is a self-inverse stream, so we
    # encrypt the desired plaintext glyph (``WORLD``) once with len_iv=0
    # before splicing it into the PostScript body.
    glyph_plain = b"WORLD"
    glyph_cipher = Type1FontUtil.charstring_encrypt(glyph_plain, len_iv=0)
    plain = (
        b"dup /Private 5 dict dup begin\n"
        b"/lenIV 0 def\n"
        b"/BlueValues [ -20 0 800 820 ] def\n"
        b"/ForceBold false def\n"
        b"2 index\n"
        b"/CharStrings 1 dict dup begin\n"
        b"/A " + str(len(glyph_cipher)).encode() + b" RD " + glyph_cipher + b" ND\n"
        b"end\n"
    )
    cipher = Type1FontUtil.eexec_encrypt(plain)

    parser = Type1Parser()
    parser.parse_binary(cipher)

    assert parser.decrypted_binary.startswith(b"dup /Private")
    assert parser.font_dict["Private"]["BlueValues"] == [-20, 0, 800, 820]
    assert parser.font_dict["Private"]["ForceBold"] is False
    assert parser.font_dict["Private"]["lenIV"] == 0
    assert parser.font_dict["CharStrings"]["A"] == glyph_plain


def test_parse_binary_rejects_segment_without_private() -> None:
    import pytest

    plain = b"dup /NotPrivate 5 dict dup begin\nend\n"
    cipher = Type1FontUtil.eexec_encrypt(plain)
    parser = Type1Parser()
    with pytest.raises(OSError, match="/Private token not found"):
        parser.parse_binary(cipher)


def test_read_subrs_populates_indexed_array() -> None:
    """``read_subrs`` should slot decrypted charstrings into
    ``font_dict["Private"]["Subrs"]`` at their declared indexes."""
    # The lexer hands the parser the *raw* charstring bytes; the parser
    # then runs the charstring cipher to recover plaintext. Pre-encrypt
    # the desired plaintext payloads with len_iv=0 so the round-trip is
    # observable as the original ASCII strings.
    cipher_a = Type1FontUtil.charstring_encrypt(b"AAA", len_iv=0)
    cipher_b = Type1FontUtil.charstring_encrypt(b"BBBB", len_iv=0)
    src = (
        b"2 array\n"
        b"dup 0 " + str(len(cipher_a)).encode() + b" RD " + cipher_a + b" NP\n"
        b"dup 1 " + str(len(cipher_b)).encode() + b" RD " + cipher_b + b" NP\n"
        b"def\n"
    )
    parser = Type1Parser()
    parser._lexer = Type1Lexer(src)
    parser.read_subrs(len_iv=0)
    subrs = parser.font_dict["Private"]["Subrs"]
    assert subrs[0] == b"AAA"
    assert subrs[1] == b"BBBB"


def test_read_char_strings_populates_glyph_map() -> None:
    """``read_char_strings`` should read the dict body into
    ``font_dict["CharStrings"]`` keyed by glyph name."""
    cipher_a = Type1FontUtil.charstring_encrypt(b"AAA", len_iv=0)
    cipher_b = Type1FontUtil.charstring_encrypt(b"BB", len_iv=0)
    src = (
        b"2 dict dup begin\n"
        b"/A " + str(len(cipher_a)).encode() + b" RD " + cipher_a + b" ND\n"
        b"/B " + str(len(cipher_b)).encode() + b" RD " + cipher_b + b" ND\n"
        b"end\n"
    )
    parser = Type1Parser()
    parser._lexer = Type1Lexer(src)
    parser.read_char_strings(len_iv=0)
    cs = parser.font_dict["CharStrings"]
    assert cs == {"A": b"AAA", "B": b"BB"}
