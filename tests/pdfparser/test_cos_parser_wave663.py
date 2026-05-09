from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError
from pypdfbox.pdfparser.cos_parser import _parse_xref_entry_line


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def test_wave663_bruteforce_object_scan_skips_embedded_obj_substrings() -> None:
    parser = _parser(b"/notanobj 99 1 0obj\n2 0 obj\n42\nendobj")

    offsets = parser.bf_search_for_objects()

    assert COSObjectKey(99, 1) not in offsets
    assert offsets[COSObjectKey(2, 0)] == parser._read_all_bytes().index(b"2 0 obj")  # noqa: SLF001


def test_wave663_bruteforce_xref_stream_scan_skips_bad_object_keyword() -> None:
    class ParserWithBadCandidate(COSParser):
        def bf_search_for_objects(self) -> dict[COSObjectKey, int]:
            return {COSObjectKey(9, 0): 0}

    parser = ParserWithBadCandidate(RandomAccessReadBuffer(b"9 0 nope << /Type /XRef >>"))

    assert parser.bf_search_for_xref(0) == -1


def test_wave663_rebuild_trailer_skips_non_object_and_non_dictionary_candidates() -> None:
    class ParserWithCandidates(COSParser):
        def bf_search_for_objects(self) -> dict[COSObjectKey, int]:
            return {
                COSObjectKey(1, 0): 0,
                COSObjectKey(2, 0): self._read_all_bytes().index(b"2 0 obj"),  # noqa: SLF001
                COSObjectKey(3, 0): self._read_all_bytes().index(b"3 0 obj"),  # noqa: SLF001
            }

    data = b"1 0 nope\n2 0 obj\n/Name\nendobj\n3 0 obj\n<4869>\nendobj\n"
    parser = ParserWithCandidates(RandomAccessReadBuffer(data))

    trailer = parser.rebuild_trailer()

    assert trailer.get_int(COSName.SIZE) == 4
    assert not trailer.contains_key(COSName.ROOT)
    assert not trailer.contains_key(COSName.get_pdf_name("Info"))


def test_wave663_rebuild_trailer_ignores_non_dictionary_parse_result() -> None:
    class ParserWithNonDictionary(COSParser):
        def bf_search_for_objects(self) -> dict[COSObjectKey, int]:
            return {COSObjectKey(1, 0): 0}

        def parse_cos_dictionary(self) -> COSDictionary:  # type: ignore[override]
            return COSInteger.get(7)  # type: ignore[return-value]

    parser = ParserWithNonDictionary(RandomAccessReadBuffer(b"1 0 obj\n<<>>\nendobj"))

    trailer = parser.rebuild_trailer()

    assert trailer.get_int(COSName.SIZE) == 2
    assert not trailer.contains_key(COSName.ROOT)


def test_wave663_parse_xref_entry_line_rejects_non_ascii_numbers() -> None:
    with pytest.raises(PDFParseError, match="malformed xref entry"):
        _parse_xref_entry_line(b"\xff 00000 n")


def test_wave663_parse_xref_entry_line_rejects_non_numeric_generation() -> None:
    with pytest.raises(PDFParseError, match="malformed xref entry"):
        _parse_xref_entry_line(b"0000000000 nope n")
