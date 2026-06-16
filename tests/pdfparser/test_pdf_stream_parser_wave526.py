from __future__ import annotations

import io
from typing import IO, Any

import pytest

from pypdfbox.contentstream import PDContentStream
from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.parse_error import PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDRectangle, PDResources


def _parser(data: bytes) -> PDFStreamParser:
    return PDFStreamParser(RandomAccessReadBuffer(data))


class _BytesContentStream(PDContentStream):
    def __init__(self, data: bytes) -> None:
        self._data = data

    def get_contents(self) -> IO[bytes]:
        return io.BytesIO(self._data)

    def get_contents_for_random_access(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_contents_for_stream_parsing(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> PDResources | None:
        return None

    def get_bbox(self) -> PDRectangle:
        return PDRectangle(0.0, 0.0, 1.0, 1.0)

    def get_matrix(self) -> Any:
        return None


def test_wave526_operator_rejects_name_object_tokens() -> None:
    with pytest.raises(ValueError, match="not allowed to start with"):
        Operator("/Name")


def test_wave526_operator_inline_predicates_and_payload_accessors() -> None:
    params = COSDictionary()
    op = Operator("BI")

    assert op.is_inline_image() is True
    assert op.has_image_data() is False
    assert op.has_image_parameters() is False

    op.set_image_data(b"abc")
    op.set_image_parameters(params)

    assert op.has_image_data() is True
    assert op.get_image_data() == b"abc"
    assert op.has_image_parameters() is True
    assert op.get_image_parameters() is params
    assert str(op) == "PDFOperator{BI}"
    assert len(op) == 2


def test_wave526_from_content_stream_and_aliases_drain_tokens() -> None:
    parser = PDFStreamParser.from_content_stream(_BytesContentStream(b"1 q"))

    assert parser.get_position() == 0
    assert parser.is_in_inline_image() is False
    assert parser.get_inline_image_depth() == 0
    assert parser.get_inline_offset() == 0
    assert [type(token) for token in parser.get_tokens()] == [COSInteger, Operator]

    parser.seek_to(0)
    assert parser.parse_stream()[1].get_name() == "q"


def test_wave526_closed_parser_returns_none_without_reading() -> None:
    parser = _parser(b"q")
    parser.close()

    assert parser.parse_next_token() is None


def test_wave526_malformed_dictionary_recovers_partial() -> None:
    # Retargeted in wave 1542: a content-stream dictionary whose final key has
    # no value (``<< /A``) is NOT a hard error. Upstream
    # ``BaseParser.parseCOSDictionary`` (which Java's ``PDFStreamParser`` uses
    # directly) logs ``Bad dictionary declaration`` and returns the name/value
    # pairs gathered so far — here the empty dictionary — without closing the
    # parser. Verified byte-exact against PDFBox 3.0.7 (``dict{}``) by the
    # ContentStreamParseFuzzProbe live oracle. The previous assertion (returns
    # ``None`` + closes the parser) was pinned to pypdfbox's old over-strict
    # container override, which wave 1542 replaced by delegating to BaseParser.
    parser = _parser(b"<< /A")

    token = parser.parse_next_token()
    assert isinstance(token, COSDictionary)
    assert token.size() == 0
    assert parser.is_closed() is False


def test_wave526_trailing_number_at_eof_parses() -> None:
    token = _parser(b"12").parse_next_token()

    assert isinstance(token, COSInteger)
    assert token.int_value() == 12


def test_wave526_malformed_inline_image_parameter_value_bails_out() -> None:
    token = _parser(b"BI /W q").parse_next_token()

    assert isinstance(token, Operator)
    assert token.get_name() == "BI"
    assert token.get_image_parameters().get_dictionary_object("W") is None
    assert token.get_image_data() is None


def test_wave526_nested_inline_image_resets_depth_on_error() -> None:
    parser = _parser(b"BI /W 1 BI")

    with pytest.raises(PDFParseError, match="Nested 'BI'"):
        parser.parse_next_token()

    assert parser.get_inline_image_depth() == 0


def test_wave526_id_at_eof_returns_empty_payload() -> None:
    token = _parser(b"ID").parse_next_token()

    assert isinstance(token, Operator)
    assert token.get_name() == "ID"
    assert token.get_image_data() == b""


def test_wave526_following_binary_data_rejects_candidate_ei() -> None:
    parser = _parser(b"\x80")

    assert parser._has_no_following_bin_data() is False  # noqa: SLF001
    assert parser.get_position() == 0


def test_wave526_long_ascii_token_after_ei_is_treated_as_binary_payload() -> None:
    parser = _parser(b"abcdefghiJ")

    assert parser._has_no_following_bin_data() is False  # noqa: SLF001
    assert parser.get_position() == 0


def test_wave526_number_pattern_helper_edges() -> None:
    from pypdfbox.pdfparser.pdf_stream_parser import _looks_like_number

    assert _looks_like_number("") is True
    assert _looks_like_number("12.5") is True
    assert _looks_like_number(COSName.get_pdf_name("NaN").get_name()) is False
