from __future__ import annotations

import pytest

from pypdfbox.cos import COSInteger
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError
from pypdfbox.pdfparser.cos_parser import _parse_xref_entry_line


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def test_wave683_indirect_reference_lookahead_rewinds_on_bad_second_number() -> None:
    class ParserWithBadSecondNumber(COSParser):
        def __init__(self) -> None:
            super().__init__(RandomAccessReadBuffer(b"1 2 R"))
            self.number_reads = 0

        def read_number(self) -> int | float:
            self.number_reads += 1
            if self.number_reads == 2:
                raise PDFParseError("bad second number")
            return super().read_number()

    parser = ParserWithBadSecondNumber()

    obj = parser.parse_direct_object()

    assert obj is COSInteger.ONE
    assert parser.position == 1


def test_wave683_indirect_reference_lookahead_rewinds_on_bad_r_keyword() -> None:
    class ParserWithBadReferenceKeyword(COSParser):
        def read_keyword(self) -> bytes:
            if self.position == 4:
                raise PDFParseError("bad reference keyword")
            return super().read_keyword()

    parser = ParserWithBadReferenceKeyword(RandomAccessReadBuffer(b"1 2 R"))

    obj = parser.parse_direct_object()

    assert obj is COSInteger.ONE
    assert parser.position == 1


def test_wave683_stream_object_rejects_wrong_keyword_after_endstream() -> None:
    parser = _parser(b"1 0 obj\n<< /Length 0 >>\nstream\nendstream\ntrailer")

    with pytest.raises(PDFParseError, match="expected 'endobj' after stream"):
        parser.parse_indirect_object_definition()


def test_wave683_stream_body_rejects_missing_endstream_keyword() -> None:
    parser = _parser(b"1 0 obj\n<< /Length 0 >>\nstream\nnotstream\nendobj")

    with pytest.raises(PDFParseError, match="expected 'endstream'"):
        parser.parse_indirect_object_definition()


def test_wave683_last_index_of_resets_after_partial_match_mismatch() -> None:
    parser = _parser(b"")

    assert parser.last_index_of(b"ab", b"acb", 3) == -1


def test_wave683_xref_object_stream_rejects_s_prefixed_non_stream_keyword() -> None:
    parser = _parser(b"1 0 obj\n<< /Type /XRef /Length 0 >>\nstan")

    with pytest.raises(PDFParseError, match="expected 'stream'"):
        parser.parse_xref_object_stream(0)


def test_wave683_xref_entry_line_rejects_non_ascii_flag() -> None:
    with pytest.raises(PDFParseError, match="malformed xref entry"):
        _parse_xref_entry_line(b"0000000000 00000 \xff")
