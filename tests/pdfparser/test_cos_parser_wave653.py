from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


class _LengthFailingBuffer(RandomAccessReadBuffer):
    def length(self) -> int:
        raise OSError("unsized")


class _ShortLengthBuffer(RandomAccessReadBuffer):
    def length(self) -> int:
        return super().length() + 5


def test_wave653_constructor_records_unsized_source_as_minus_one() -> None:
    parser = COSParser(_LengthFailingBuffer(b""))

    assert parser.get_file_len() == -1


def test_wave653_indirect_reference_lookahead_rewinds_when_second_number_fails() -> None:
    class ParserWithBadSecondNumber(COSParser):
        def __init__(self) -> None:
            super().__init__(RandomAccessReadBuffer(b"7 8 R"))
            self.calls = 0

        def read_number(self) -> int:
            self.calls += 1
            if self.calls == 2:
                raise PDFParseError("bad second number")
            return super().read_number()

    parser = ParserWithBadSecondNumber()

    parsed = parser.parse_direct_object()

    assert isinstance(parsed, COSInteger)
    assert parsed.int_value() == 7
    assert parser.position == 1


def test_wave653_indirect_reference_lookahead_rewinds_when_r_keyword_fails() -> None:
    class ParserWithBadReferenceKeyword(COSParser):
        def __init__(self) -> None:
            super().__init__(RandomAccessReadBuffer(b"7 8 R"))

        def read_keyword(self) -> bytes:
            if self.peek_byte() == ord("R"):
                raise PDFParseError("bad R")
            return super().read_keyword()

    parser = ParserWithBadReferenceKeyword()

    parsed = parser.parse_direct_object()

    assert isinstance(parsed, COSInteger)
    assert parsed.int_value() == 7
    assert parser.position == 1


def test_wave653_stream_object_rejects_wrong_endstream_and_endobj_keywords() -> None:
    with pytest.raises(PDFParseError, match="expected 'endstream'"):
        _parser(
            b"1 0 obj << /Length 0 >> stream\nwrong\nendobj"
        ).parse_indirect_object_definition()

    with pytest.raises(PDFParseError, match="expected 'endobj' after stream"):
        _parser(
            b"1 0 obj << /Length 0 >> stream\nendstream\nwrong"
        ).parse_indirect_object_definition()


def test_wave653_peek_two_bytes_handles_eof_and_single_remaining_byte() -> None:
    empty = _parser(b"")
    single = _parser(b"X")

    assert empty._peek_two_bytes() == (-1, -1)  # noqa: SLF001
    assert single._peek_two_bytes() == (ord("X"), -1)  # noqa: SLF001
    assert single.position == 0


def test_wave653_last_index_of_resets_after_partial_reverse_match() -> None:
    parser = _parser(b"")

    assert parser.last_index_of(b"ab", b"acb", 3) == -1


def test_wave653_xref_object_stream_rejects_non_stream_s_keyword() -> None:
    parser = _parser(b"9 0 obj << /Type /XRef /Length 0 >> stub")

    with pytest.raises(PDFParseError, match="expected 'stream'"):
        parser.parse_xref_object_stream(0)


def test_wave653_read_all_bytes_stops_when_source_ends_before_reported_length() -> None:
    parser = COSParser(_ShortLengthBuffer(b"abc"))
    parser.seek(2)

    assert parser._read_all_bytes() == b"abc"  # noqa: SLF001
    assert parser.position == 2


def test_wave653_bruteforce_object_scan_skips_headers_without_object_number() -> None:
    parser = _parser(b"7 obj\n1 0 obj\n<< /Type /Catalog >>\nendobj")

    offsets = parser.bf_search_for_objects()

    assert COSObjectKey(1, 0) in offsets
    assert len(offsets) == 1


def test_wave653_bruteforce_xref_scan_skips_non_xref_object_stream_candidates() -> None:
    parser = _parser(b"1 0 obj\n<< /Type /Catalog >>\nendobj")

    assert parser.bf_search_for_xref(0) == -1


def test_wave653_rebuild_trailer_skips_malformed_candidate_offsets() -> None:
    class ParserWithBadCandidate(COSParser):
        def bf_search_for_objects(self) -> dict[COSObjectKey, int]:
            return {COSObjectKey(1, 0): 0}

    parser = ParserWithBadCandidate(RandomAccessReadBuffer(b"not an object"))

    assert parser.rebuild_trailer().get_int("Size") == 2


def test_wave653_rebuild_trailer_skips_non_dictionary_object_body() -> None:
    class ParserWithScalarCandidate(COSParser):
        def bf_search_for_objects(self) -> dict[COSObjectKey, int]:
            return {COSObjectKey(1, 0): 0}

    parser = ParserWithScalarCandidate(RandomAccessReadBuffer(b"1 0 obj 42 endobj"))

    trailer = parser.rebuild_trailer()

    assert trailer.get_int("Size") == 2
    assert not trailer.contains_key(COSName.ROOT)


def test_wave653_build_stream_from_dict_preserves_entries_without_document() -> None:
    src = COSDictionary()
    src.set_item("Length", COSInteger.get(0))

    stream = _parser(b"")._build_stream_from_dict(src)  # noqa: SLF001

    assert isinstance(stream, COSStream)
    assert stream.get_int("Length") == 0
