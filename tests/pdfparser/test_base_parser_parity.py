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


# ---------- string constants (upstream parity) ----------


def test_upstream_string_constants_match_upstream_values() -> None:
    assert BaseParser.DEF == "def"
    assert BaseParser.ENDOBJ_STRING == "endobj"
    assert BaseParser.ENDSTREAM_STRING == "endstream"
    assert BaseParser.STREAM_STRING == "stream"


def test_upstream_ascii_byte_constants() -> None:
    assert BaseParser.ASCII_LF == 0x0A
    assert BaseParser.ASCII_CR == 0x0D
    assert BaseParser.ASCII_SPACE == 0x20


def test_upstream_object_number_thresholds() -> None:
    # Per upstream: object numbers must be < 10^10, generation <= 65535.
    assert BaseParser.OBJECT_NUMBER_THRESHOLD == 10_000_000_000
    assert BaseParser.GENERATION_NUMBER_THRESHOLD == 65535


# ---------- is_end_of_name ----------


def test_is_end_of_name_terminates_on_pdf_delimiters() -> None:
    for ch in (
        BaseParser.ASCII_SPACE, BaseParser.ASCII_CR, BaseParser.ASCII_LF,
        0x09, 0x00, 0x0C,
        ord(">"), ord("<"), ord("["), ord("]"), ord("("), ord(")"),
        ord("/"), ord("%"),
    ):
        assert BaseParser.is_end_of_name(ch)


def test_is_end_of_name_negative_byte_terminates() -> None:
    assert BaseParser.is_end_of_name(-1)


def test_is_end_of_name_regular_char_does_not_terminate() -> None:
    for ch in b"AaZz09_-.@":
        assert not BaseParser.is_end_of_name(ch)


# ---------- is_space / no-arg classifiers ----------


def test_is_space_only_matches_ascii_space() -> None:
    assert BaseParser.is_space(0x20)
    assert not BaseParser.is_space(0x09)  # tab is whitespace, not space
    assert not BaseParser.is_space(0x0A)


def test_is_space_at_peeks_without_consuming() -> None:
    p = parser(b" abc")
    assert p.is_space_at()
    assert p.position == 0
    p.read()
    assert not p.is_space_at()


def test_is_whitespace_at_peeks_without_consuming() -> None:
    p = parser(b"\tabc")
    assert p.is_whitespace_at()
    assert p.position == 0
    p.read()
    assert not p.is_whitespace_at()


def test_is_digit_at_peeks_without_consuming() -> None:
    p = parser(b"7x")
    assert p.is_digit_at()
    assert p.position == 0
    p.read()
    assert not p.is_digit_at()


def test_is_eol_at_peeks_without_consuming() -> None:
    p = parser(b"\rx")
    assert p.is_eol_at()
    assert p.position == 0
    p.read()
    assert not p.is_eol_at()


def test_is_eol_at_returns_false_at_eof() -> None:
    p = parser(b"")
    assert not p.is_eol_at()


# ---------- is_closing ----------


def test_is_closing_no_arg_peeks() -> None:
    p = parser(b"]rest")
    assert p.is_closing()
    assert p.position == 0
    p.read()
    assert not p.is_closing()


def test_is_closing_with_arg() -> None:
    p = parser(b"")
    assert p.is_closing(ord("]"))
    assert not p.is_closing(ord("["))
    assert not p.is_closing(-1)


# ---------- skip_spaces (alias) ----------


def test_skip_spaces_is_alias_of_skip_whitespace() -> None:
    p = parser(b"   \t\nabc")
    p.skip_spaces()
    assert p.read() == ord("a")


def test_skip_spaces_skips_comments_like_skip_whitespace() -> None:
    p = parser(b"% comment\nrest")
    p.skip_spaces()
    assert p.read() == ord("r")


# ---------- skip_linebreak ----------


def test_skip_linebreak_consumes_lf() -> None:
    p = parser(b"\nrest")
    assert p.skip_linebreak() is True
    assert p.read() == ord("r")


def test_skip_linebreak_consumes_cr() -> None:
    p = parser(b"\rrest")
    assert p.skip_linebreak() is True
    assert p.read() == ord("r")


def test_skip_linebreak_consumes_crlf_as_one_unit() -> None:
    p = parser(b"\r\nrest")
    assert p.skip_linebreak() is True
    assert p.position == 2
    assert p.read() == ord("r")


def test_skip_linebreak_returns_false_when_no_break() -> None:
    p = parser(b"abc")
    assert p.skip_linebreak() is False
    assert p.position == 0


def test_skip_linebreak_at_eof_returns_false() -> None:
    p = parser(b"")
    assert p.skip_linebreak() is False


# ---------- skip_white_spaces (post-stream) ----------


def test_skip_white_spaces_eats_lf_only() -> None:
    p = parser(b"\nDATA")
    p.skip_white_spaces()
    assert p.read() == ord("D")


def test_skip_white_spaces_eats_crlf() -> None:
    p = parser(b"\r\nDATA")
    p.skip_white_spaces()
    assert p.read() == ord("D")


def test_skip_white_spaces_tolerates_leading_spaces() -> None:
    # brother_scan_cover.pdf-style: stream<sp><sp>\n
    p = parser(b"  \nDATA")
    p.skip_white_spaces()
    assert p.read() == ord("D")


def test_skip_white_spaces_no_eol_rewinds_one() -> None:
    # If there's no EOL and no leading space, position should stay just
    # before the first non-space byte.
    p = parser(b"DATA")
    p.skip_white_spaces()
    assert p.position == 0
    assert p.read() == ord("D")


# ---------- read_line ----------


def test_read_line_terminates_at_lf() -> None:
    p = parser(b"hello\nworld")
    assert p.read_line() == "hello"
    assert p.read() == ord("w")


def test_read_line_terminates_at_cr() -> None:
    p = parser(b"hello\rworld")
    assert p.read_line() == "hello"
    assert p.read() == ord("w")


def test_read_line_consumes_crlf_as_one_eol() -> None:
    p = parser(b"hello\r\nworld")
    assert p.read_line() == "hello"
    assert p.read() == ord("w")


def test_read_line_returns_at_eof_without_eol() -> None:
    p = parser(b"trailing")
    assert p.read_line() == "trailing"
    assert p.is_eof()


def test_read_line_raises_at_eof_when_called() -> None:
    p = parser(b"")
    with pytest.raises(PDFParseError):
        p.read_line()


# ---------- read_expected_char ----------


def test_read_expected_char_match_int() -> None:
    p = parser(b"<<")
    p.read_expected_char(ord("<"))
    assert p.read() == ord("<")


def test_read_expected_char_match_str() -> None:
    p = parser(b"[abc]")
    p.read_expected_char("[")
    assert p.read() == ord("a")


def test_read_expected_char_mismatch_raises() -> None:
    p = parser(b"X")
    with pytest.raises(PDFParseError):
        p.read_expected_char("Y")


def test_read_expected_char_str_too_long_raises() -> None:
    p = parser(b"<<")
    with pytest.raises(ValueError):
        p.read_expected_char("<<")


# ---------- read_object_number / read_generation_number ----------


def test_read_object_number_basic() -> None:
    p = parser(b"42 ")
    assert p.read_object_number() == 42


def test_read_object_number_skips_leading_whitespace() -> None:
    p = parser(b"   7 0 R")
    assert p.read_object_number() == 7


def test_read_object_number_negative_raises() -> None:
    p = parser(b"-1 ")
    with pytest.raises(PDFParseError):
        p.read_object_number()


def test_read_object_number_too_large_raises() -> None:
    p = parser(b"99999999999 ")  # >= 10**10
    with pytest.raises(PDFParseError):
        p.read_object_number()


def test_read_object_number_at_threshold_raises() -> None:
    # Exactly OBJECT_NUMBER_THRESHOLD must raise (>= threshold).
    p = parser(b"10000000000 ")
    with pytest.raises(PDFParseError):
        p.read_object_number()


def test_read_generation_number_basic() -> None:
    p = parser(b"0 ")
    assert p.read_generation_number() == 0


def test_read_generation_number_max_allowed() -> None:
    p = parser(b"65535 ")
    assert p.read_generation_number() == 65535


def test_read_generation_number_too_large_raises() -> None:
    p = parser(b"65536 ")
    with pytest.raises(PDFParseError):
        p.read_generation_number()


def test_read_generation_number_negative_raises() -> None:
    p = parser(b"-1 ")
    with pytest.raises(PDFParseError):
        p.read_generation_number()
