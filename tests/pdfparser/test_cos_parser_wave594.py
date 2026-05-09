from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def test_wave594_header_predicates_restore_position_on_success_and_failure() -> None:
    parser = _parser(b"noise\n%PDF-1.7\nbody")
    parser.seek(3)

    assert parser.has_pdf_header()
    assert parser.position == 3
    assert not parser.has_fdf_header()
    assert parser.position == 3


def test_wave594_header_without_version_uses_default_versions() -> None:
    assert _parser(b"%PDF-\n").parse_pdf_header() == 1.4
    assert _parser(b"%FDF-\n").parse_fdf_header() == 1.0


def test_wave594_file_len_accessors_can_override_constructor_length() -> None:
    parser = _parser(b"abc")

    assert parser.get_file_len() == 3

    parser.set_file_len(27)

    assert parser.get_file_len() == 27


def test_wave594_parse_xref_table_keeps_first_offset_for_duplicate_key() -> None:
    data = (
        b"xref\n"
        b"2 1\n"
        b"0000000010 00000 n \n"
        b"2 1\n"
        b"0000000099 00000 n \n"
        b"trailer\n<< /Size 3 >>\n"
    )
    table: dict[COSObjectKey, int] = {}

    assert _parser(data).parse_xref_table(0, table)
    assert table[COSObjectKey(2, 0)] == 10


def test_wave594_parse_object_stream_rejects_first_beyond_decoded_length() -> None:
    doc = COSDocument()
    try:
        stream = COSStream(scratch_file=doc.scratch_file)
        stream.set_item("Type", COSName.get_pdf_name("ObjStm"))
        stream.set_item("N", COSInteger.get(1))
        stream.set_item("First", COSInteger.get(99))
        stream.set_raw_data(b"8 0 true")
        doc.get_object_from_pool(COSObjectKey(4, 0)).set_object(stream)

        with pytest.raises(PDFParseError, match="/First 99 exceeds decoded length"):
            COSParser(RandomAccessReadBuffer(b""), document=doc).parse_object_stream(4)
    finally:
        doc.close()
