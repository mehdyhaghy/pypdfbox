from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser, PDFParseError


def parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


# ---------- upstream-name aliases: peek / read / unread ----------


def test_peek_does_not_advance_position() -> None:
    p = parser(b"abc")
    assert p.peek() == ord("a")
    assert p.position == 0
    assert p.peek() == ord("a")
    assert p.position == 0


def test_peek_returns_minus_one_at_eof() -> None:
    p = parser(b"")
    assert p.peek() == -1


def test_read_advances_position_one_byte() -> None:
    p = parser(b"xyz")
    assert p.read() == ord("x")
    assert p.position == 1
    assert p.read() == ord("y")
    assert p.position == 2


def test_read_returns_minus_one_at_eof() -> None:
    p = parser(b"a")
    assert p.read() == ord("a")
    assert p.read() == -1


def test_unread_rewinds_one_byte() -> None:
    p = parser(b"abc")
    assert p.read() == ord("a")
    p.unread(ord("a"))
    assert p.position == 0
    assert p.read() == ord("a")


def test_unread_at_position_zero_is_noop() -> None:
    p = parser(b"abc")
    p.unread(0x00)
    assert p.position == 0


# ---------- is_eof ----------


def test_is_eof_false_when_bytes_remain() -> None:
    p = parser(b"hello")
    assert not p.is_eof()
    p.read()
    assert not p.is_eof()


def test_is_eof_true_after_consuming_all_bytes() -> None:
    p = parser(b"ab")
    p.read()
    p.read()
    assert p.is_eof()


def test_is_eof_true_for_empty_source() -> None:
    p = parser(b"")
    assert p.is_eof()


# ---------- skip_whitespace ----------


def test_skip_whitespace_skips_spaces() -> None:
    p = parser(b"   abc")
    p.skip_whitespace()
    assert p.position == 3
    assert p.read() == ord("a")


def test_skip_whitespace_skips_tabs_cr_lf_ff_nul() -> None:
    p = parser(b"\x00\t\n\x0c\r abc")
    p.skip_whitespace()
    assert p.read() == ord("a")


def test_skip_whitespace_skips_pdf_comments_to_eol() -> None:
    p = parser(b"% this is a comment\nabc")
    p.skip_whitespace()
    assert p.read() == ord("a")


def test_skip_whitespace_skips_multiple_comments_and_whitespace() -> None:
    p = parser(b"  % first\n   % second\r\n  abc")
    p.skip_whitespace()
    assert p.read() == ord("a")


def test_skip_whitespace_at_eof_is_safe() -> None:
    p = parser(b"   ")
    p.skip_whitespace()
    assert p.is_eof()


def test_skip_whitespace_no_op_when_starting_on_token() -> None:
    p = parser(b"abc")
    p.skip_whitespace()
    assert p.position == 0


# ---------- read_int ----------


def test_read_int_unsigned() -> None:
    p = parser(b"123 ")
    assert p.read_int() == 123


def test_read_int_signed_negative() -> None:
    p = parser(b"-42 ")
    assert p.read_int() == -42


def test_read_int_signed_positive() -> None:
    p = parser(b"+7 ")
    assert p.read_int() == 7


def test_read_int_stops_at_non_digit() -> None:
    p = parser(b"100abc")
    assert p.read_int() == 100
    assert p.read() == ord("a")


def test_read_int_stops_at_eof() -> None:
    p = parser(b"99")
    assert p.read_int() == 99
    assert p.is_eof()


def test_read_int_raises_on_non_numeric() -> None:
    p = parser(b"abc")
    with pytest.raises(PDFParseError):
        p.read_int()


def test_read_int_raises_on_lone_sign() -> None:
    p = parser(b"-x")
    with pytest.raises(PDFParseError):
        p.read_int()


# ---------- read_long ----------


def test_read_long_handles_large_value() -> None:
    p = parser(b"9999999999999 ")
    assert p.read_long() == 9999999999999


def test_read_long_negative() -> None:
    p = parser(b"-12345678901 ")
    assert p.read_long() == -12345678901


def test_read_long_matches_read_int_for_normal_values() -> None:
    p = parser(b"42")
    q = parser(b"42")
    assert p.read_long() == q.read_int()


# ---------- read_string ----------


def test_read_string_reads_token_until_whitespace() -> None:
    p = parser(b"hello world")
    assert p.read_string() == "hello"
    assert p.peek() == ord(" ")


def test_read_string_terminates_at_eof() -> None:
    p = parser(b"abcdef")
    assert p.read_string() == "abcdef"
    assert p.is_eof()


def test_read_string_empty_when_starting_on_whitespace() -> None:
    p = parser(b" abc")
    assert p.read_string() == ""
    assert p.position == 0


def test_read_string_stops_at_newline() -> None:
    p = parser(b"foo\nbar")
    assert p.read_string() == "foo"


# ---------- static character classifiers (upstream-name parity) ----------


def test_is_whitespace_static_helper() -> None:
    assert BaseParser.is_whitespace(0x20)
    assert BaseParser.is_whitespace(0x0A)
    assert not BaseParser.is_whitespace(ord("A"))


def test_is_digit_static_helper() -> None:
    assert BaseParser.is_digit(ord("0"))
    assert BaseParser.is_digit(ord("9"))
    assert not BaseParser.is_digit(ord("a"))


def test_is_eol_static_helper() -> None:
    assert BaseParser.is_eol(0x0A)
    assert BaseParser.is_eol(0x0D)
    assert not BaseParser.is_eol(0x20)
    assert not BaseParser.is_eol(ord("A"))
