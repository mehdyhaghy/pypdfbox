from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser, PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser


def _base_parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


def _stream_parser(data: bytes) -> PDFStreamParser:
    return PDFStreamParser(RandomAccessReadBuffer(data))


class _NeverEofBuffer(RandomAccessReadBuffer):
    def is_eof(self) -> bool:
        return False


def test_wave783_require_byte_raises_at_eof_without_advancing() -> None:
    parser = _base_parser(b"")

    with pytest.raises(PDFParseError, match="unexpected EOF"):
        parser.require_byte()

    assert parser.position == 0


def test_wave783_read_name_falls_back_for_raw_latin1_byte() -> None:
    parser = _base_parser(b"/caf\xe9 next")

    assert parser.read_name() == "caf\xe9"
    assert parser.peek_byte() == ord(" ")


def test_wave783_check_for_end_of_string_short_probe_keeps_depth() -> None:
    parser = _base_parser(b"\n/")

    assert parser._check_for_end_of_string(2) == 2  # noqa: SLF001
    assert parser.position == 0


def test_wave783_consume_escape_at_eof_leaves_depth_unchanged() -> None:
    parser = _base_parser(b"")
    out = bytearray()

    assert parser._consume_escape(out, 3) == 3  # noqa: SLF001
    assert out == bytearray()


def test_wave783_inline_image_data_breaks_when_false_eof_reports_eof_byte() -> None:
    parser = PDFStreamParser(_NeverEofBuffer(b"ID "))

    token = parser.parse_next_token()

    assert isinstance(token, Operator)
    assert token.get_name() == "ID"
    assert token.get_image_data() == b""


def test_wave783_inline_probe_rejects_long_non_numeric_ascii_token() -> None:
    parser = _stream_parser(b"ABCDEFGHIJ")

    assert parser._has_no_following_bin_data() is False  # noqa: SLF001
    assert parser.get_position() == 0


def test_wave783_inline_probe_accepts_numeric_operator_probe() -> None:
    parser = _stream_parser(b" 12.5 ")

    assert parser._has_no_following_bin_data() is True  # noqa: SLF001
    assert parser.get_position() == 0
