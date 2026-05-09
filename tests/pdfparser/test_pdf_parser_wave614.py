from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefType


def _parser(data: bytes = b"") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _xref_stream(widths: list[int], raw: bytes) -> COSStream:
    stream = COSStream()
    w = COSArray()
    for width in widths:
        w.add(COSInteger.get(width))
    stream.set_item("W", w)
    stream.set_raw_data(raw)
    return stream


def test_wave614_read_stream_body_resolves_loaded_indirect_length() -> None:
    parser = _parser(b"ABC\nendstream")
    length_ref = COSObject(9, 0, resolved=COSInteger.get(3))
    stream = COSStream()
    stream.set_item("Length", length_ref)

    parser._read_stream_body(stream)  # noqa: SLF001

    assert stream.get_raw_data() == b"ABC"


def test_wave614_decode_xref_stream_registers_free_and_compressed_entries() -> None:
    parser = _parser()
    parser.get_xref_trailer_resolver().begin_section(0)
    stream = _xref_stream([1, 1, 1], b"\x00\x05\x02\x02\x08\x03")
    index = COSArray()
    index.add(COSInteger.get(3))
    index.add(COSInteger.get(2))
    stream.set_item("Index", index)

    parser._decode_xref_stream_entries(stream)  # noqa: SLF001

    table = parser.get_xref_trailer_resolver().get_xref_table()
    free = table[COSObjectKey(3, 2)]
    compressed = table[COSObjectKey(4, 0)]
    assert free.type is XrefType.STREAM
    assert free.offset == 5
    assert free.compressed_index == -1
    assert compressed.type is XrefType.COMPRESSED
    assert compressed.offset == 8
    assert compressed.compressed_index == 3


def test_wave614_handle_xref_stream_requires_stream_keyword() -> None:
    parser = _parser(b"9 0 obj\n<< /Type /XRef /Size 0 /W [1 1 1] >>\nendobj")
    doc = COSDocument()
    parser._document = doc  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001

    try:
        with pytest.raises(PDFParseError, match="missing 'stream' keyword"):
            parser._handle_xref_stream_at(0)  # noqa: SLF001
    finally:
        doc.close()


def test_wave614_load_indirect_object_tolerates_mismatched_header_numbers() -> None:
    parser = _parser(b"2 0 obj\n/Name\nendobj")
    doc = COSDocument()
    parser._document = doc  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001

    try:
        parsed = parser._load_indirect_object_at(0, COSObject(1, 0))  # noqa: SLF001

        assert parsed is COSName.get_pdf_name("Name")
    finally:
        doc.close()
