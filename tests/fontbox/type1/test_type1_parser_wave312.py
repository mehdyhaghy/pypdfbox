from __future__ import annotations

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import TOKEN_STRING, Type1Lexer, Type1Parser


def test_wave312_lexer_drops_escaped_lf_continuation_in_string() -> None:
    lexer = Type1Lexer("(Alpha\\\nBeta)")

    assert lexer.next_token() == (TOKEN_STRING, "AlphaBeta")


def test_wave312_lexer_drops_escaped_crlf_continuation_in_string() -> None:
    lexer = Type1Lexer("(Alpha\\\r\nBeta)")

    assert lexer.next_token() == (TOKEN_STRING, "AlphaBeta")


def test_wave312_parser_drops_font_info_string_continuation() -> None:
    header = b"""
%!PS-AdobeFont-1.0: Wave312 001.000
12 dict begin
/FontInfo 1 dict dup begin
  /Notice (Alpha\\
Beta) readonly def
end readonly def
/FontName /Wave312 def
"""

    parser = Type1Parser()
    parser.parse(header, Type1FontUtil.eexec_encrypt(b""))

    assert parser.font_dict["FontInfo"]["Notice"] == "AlphaBeta"
