from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSInteger, COSObject, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefEntry, XrefType


def _parser(data: bytes = b"") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def test_wave593_find_startxref_can_skip_bounds_validation() -> None:
    data = b"%PDF-1.4\nstartxref\n999\n%%EOF"

    assert _parser(data).find_startxref_offset(validate_bounds=False) == 999

    with pytest.raises(PDFParseError, match="out of file bounds"):
        _parser(data).find_startxref_offset()


def test_wave593_populate_document_skips_free_entries_and_lazy_loads_in_use() -> None:
    data = b"1 0 obj\n42\nendobj\n"
    parser = _parser(data)
    doc = parser._document = COSDocument()  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001
    parser.get_xref_trailer_resolver().begin_section(0)
    parser.get_xref_trailer_resolver().set_entry(
        COSObjectKey(0, 65535),
        XrefEntry(type=XrefType.TABLE, offset=0, compressed_index=-1),
    )
    parser.get_xref_trailer_resolver().set_entry(
        COSObjectKey(1, 0),
        XrefEntry(type=XrefType.TABLE, offset=0),
    )

    try:
        parser.populate_document()

        assert not doc.has_object(COSObjectKey(0, 65535))
        loaded = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
        assert loaded is COSInteger.get(42)
    finally:
        doc.close()


def test_wave593_read_stream_body_reports_missing_endstream_keyword() -> None:
    parser = _parser(b"ABC\nnotstream")
    stream = COSStream()
    stream.set_item("Length", COSInteger.get(3))

    with pytest.raises(PDFParseError, match="expected 'endstream'"):
        parser._read_stream_body(stream)  # noqa: SLF001

    assert stream.get_raw_data() == b"ABC"


def test_wave593_resolve_stream_length_rejects_indirect_length_reference() -> None:
    parser = _parser()
    stream = COSStream()
    stream.set_item("Length", COSObject(9, 0))

    with pytest.raises(PDFParseError, match="missing or malformed /Length"):
        parser._resolve_stream_length(stream)  # noqa: SLF001
