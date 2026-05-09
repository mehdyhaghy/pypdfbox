from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser, PDFParseError


def parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


def test_seek_repositions_parser_for_reread() -> None:
    p = parser(b"abcdef")

    p.seek(3)
    assert p.position == 3
    assert p.read_byte() == ord("d")

    p.seek(1)
    assert p.read_string() == "bcdef"


def test_read_until_eol_at_eof_returns_remaining_bytes() -> None:
    p = parser(b"last line")

    assert p.read_until_eol() == b"last line"
    assert p.is_eof()


def test_skip_white_spaces_consumes_lone_cr_before_stream_data() -> None:
    p = parser(b"\rDATA")

    p.skip_white_spaces()

    assert p.read_byte() == ord("D")


def test_skip_white_spaces_at_eof_after_spaces_is_safe() -> None:
    p = parser(b"   ")

    p.skip_white_spaces()

    assert p.is_eof()


def test_read_line_decodes_non_ascii_bytes_as_latin1() -> None:
    p = parser(b"caf\xe9\nnext")

    assert p.read_line() == "café"
    assert p.read_byte() == ord("n")


def test_read_name_with_single_hex_digit_keeps_hash_and_digit() -> None:
    p = parser(b"/Name#2 rest")

    assert p.read_name() == "Name#2"
    assert p.read_byte() == ord(" ")


def test_literal_string_malformed_escaped_close_can_end_before_name() -> None:
    p = parser(b"(abc\\)\n/Next")

    assert p.read_literal_string() == b"abc\\"
    assert p.read_byte() == ord("\n")


def test_hex_string_invalid_digit_reports_parse_error() -> None:
    with pytest.raises(PDFParseError, match="invalid hex digit"):
        parser(b"<0G>").read_hex_string()


def test_hex_string_unterminated_reports_parse_error() -> None:
    with pytest.raises(PDFParseError, match="unterminated hex string"):
        parser(b"<00").read_hex_string()


def test_read_keyword_requires_alphabetic_start_and_rewinds() -> None:
    p = parser(b"1obj")

    with pytest.raises(PDFParseError, match="expected keyword"):
        p.read_keyword()

    assert p.position == 0
    assert p.read_byte() == ord("1")


def test_read_keyword_raises_at_eof() -> None:
    with pytest.raises(PDFParseError, match="expected keyword"):
        parser(b"").read_keyword()


def test_read_string_decodes_non_ascii_bytes_as_latin1() -> None:
    p = parser(b"caf\xe9 ")

    assert p.read_string() == "café"
    assert p.peek_byte() == ord(" ")
