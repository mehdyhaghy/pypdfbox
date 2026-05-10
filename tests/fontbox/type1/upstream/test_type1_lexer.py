"""Ported upstream tests for ``Type1Lexer``.

Upstream PDFBox ships no dedicated ``Type1LexerTest.java`` (the lexer is
package-private and exercised through ``Type1Parser`` integration). This
file mirrors the upstream-shaped read helpers' contract — each test
exercises one of the methods on Type1Lexer.java and locks in the
behaviour we just promoted to public methods so future re-ports stay
diffable.

When upstream eventually adds a ``Type1LexerTest`` we should re-port
the cases here and keep filenames upstream-identical.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_CHARSTRING,
    TOKEN_INTEGER,
    TOKEN_NAME,
    TOKEN_REAL,
    TOKEN_STRING,
    Type1Lexer,
)

# ---------- get_char ----------


def test_get_char_returns_chars_in_order() -> None:
    lex = Type1Lexer("AB")
    assert lex.get_char() == "A"
    assert lex.get_char() == "B"


def test_get_char_raises_on_premature_eof() -> None:
    lex = Type1Lexer("")
    with pytest.raises(OSError, match="Premature end of buffer"):
        lex.get_char()


# ---------- peek_kind ----------


def test_peek_kind_matches_first_token_kind() -> None:
    lex = Type1Lexer("/Foo 42")
    assert lex.peek_kind("literal")
    assert not lex.peek_kind("integer")


def test_peek_kind_at_eof_returns_false() -> None:
    lex = Type1Lexer("")
    assert not lex.peek_kind("name")


# ---------- try_read_number ----------


def test_try_read_number_reads_integer() -> None:
    lex = Type1Lexer("42 def")
    assert lex.try_read_number() == (TOKEN_INTEGER, 42)


def test_try_read_number_reads_real() -> None:
    lex = Type1Lexer("3.14 ")
    assert lex.try_read_number() == (TOKEN_REAL, 3.14)


def test_try_read_number_reads_radix_form() -> None:
    # PostScript radix: 16#FF == 255.
    lex = Type1Lexer("16#FF ")
    assert lex.try_read_number() == (TOKEN_INTEGER, 255)


def test_try_read_number_rewinds_on_non_number() -> None:
    lex = Type1Lexer("foo")
    saved = lex.remaining()
    assert lex.try_read_number() is None
    assert lex.remaining() == saved


# ---------- read_regular ----------


def test_read_regular_stops_at_whitespace() -> None:
    lex = Type1Lexer("FontName def")
    assert lex.read_regular() == "FontName"


def test_read_regular_stops_at_delimiter() -> None:
    lex = Type1Lexer("FontName/Other")
    assert lex.read_regular() == "FontName"


def test_read_regular_returns_none_on_immediate_delimiter() -> None:
    lex = Type1Lexer("/Foo")
    assert lex.read_regular() is None


# ---------- read_comment ----------


def test_read_comment_reads_to_eol() -> None:
    lex = Type1Lexer("hello world\nrest")
    assert lex.read_comment() == "hello world"
    # cursor is at the newline.
    assert lex.get_char() == "\n"


def test_read_comment_handles_eof_without_eol() -> None:
    lex = Type1Lexer("trailing")
    assert lex.read_comment() == "trailing"


# ---------- read_string ----------


def test_read_string_balanced_parens() -> None:
    lex = Type1Lexer("hello (nested) world)tail")
    # Caller has already consumed the opening "(" upstream; we mirror.
    assert lex.read_string() == (TOKEN_STRING, "hello (nested) world")
    assert lex.remaining() == "tail"


def test_read_string_handles_escape_sequences() -> None:
    lex = Type1Lexer(r"a\nb\tc\\d\(e\))")
    assert lex.read_string() == (TOKEN_STRING, "a\nb\tc\\d(e))"[:-1])


def test_read_string_octal_escape() -> None:
    # \101 == 'A'
    lex = Type1Lexer("X\\101Y)")
    assert lex.read_string() == (TOKEN_STRING, "XAY")


def test_read_string_returns_none_on_unterminated() -> None:
    lex = Type1Lexer("never closed")
    assert lex.read_string() is None


# ---------- read_char_string ----------


def test_read_char_string_captures_raw_bytes() -> None:
    payload = b"\x00\x01\xff\x80abc"
    src = b" " + payload + b" tail"
    lex = Type1Lexer(src)
    kind, data = lex.read_char_string(len(payload))
    assert kind == TOKEN_CHARSTRING
    assert data == payload


def test_read_char_string_rejects_oversized_length() -> None:
    lex = Type1Lexer(" abc")
    with pytest.raises(OSError, match="larger than input"):
        lex.read_char_string(99999)


def test_read_char_string_premature_eof() -> None:
    # length fits the buffer's total size guard but exceeds bytes
    # remaining after the cursor + delimiter byte.
    lex = Type1Lexer(b"abcde")
    # advance cursor past 4 bytes so only one byte (the delimiter)
    # remains; asking for 1 raw byte would then hit EOF after consuming
    # the delimiter.
    for _ in range(4):
        lex.get_char()
    with pytest.raises(OSError, match="Premature"):
        lex.read_char_string(1)


# ---------- read_token ----------


def test_read_token_basic_name() -> None:
    lex = Type1Lexer("def")
    assert lex.read_token() == (TOKEN_NAME, "def")


def test_read_token_charstring_after_int() -> None:
    # "<INT> RD <space> <bytes>" → CHARSTRING capture.
    payload = b"\x10\x20\x30"
    src = b"3 RD " + payload + b" ND"
    lex = Type1Lexer(src)
    int_tok = lex.read_token()
    assert int_tok == (TOKEN_INTEGER, 3)
    cs_tok = lex.read_token(int_tok)
    assert cs_tok == (TOKEN_CHARSTRING, payload)
    nd_tok = lex.read_token()
    assert nd_tok == (TOKEN_NAME, "ND")
