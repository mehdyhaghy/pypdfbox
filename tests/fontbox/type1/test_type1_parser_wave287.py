from __future__ import annotations

from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_CHARSTRING,
    TOKEN_INTEGER,
    TOKEN_LITERAL,
    Type1Lexer,
)


def test_lexer_negative_charstring_length_does_not_rewind() -> None:
    lexer = Type1Lexer("/A -1 RD /Next 1 def")

    assert lexer.next_token() == (TOKEN_LITERAL, "A")
    assert lexer.next_token() == (TOKEN_INTEGER, -1)
    assert lexer.next_token() == (TOKEN_CHARSTRING, b"")
    assert lexer.next_token() == (TOKEN_LITERAL, "Next")
    assert lexer.next_token() == (TOKEN_INTEGER, 1)


def test_lexer_truncated_charstring_payload_returns_available_bytes() -> None:
    lexer = Type1Lexer("/A 5 RD abc")

    assert lexer.next_token() == (TOKEN_LITERAL, "A")
    assert lexer.next_token() == (TOKEN_INTEGER, 5)
    assert lexer.next_token() == (TOKEN_CHARSTRING, b"abc")
    assert lexer.next_token() is None
