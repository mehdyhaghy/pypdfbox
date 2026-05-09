from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefType


def _parser(data: bytes = b"") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def test_wave583_decode_xref_stream_treats_unknown_entry_type_as_free() -> None:
    parser = _parser()
    parser.get_xref_trailer_resolver().begin_section(0)

    body = COSStream()
    widths = COSArray()
    widths.add(COSInteger.get(1))
    widths.add(COSInteger.get(1))
    widths.add(COSInteger.get(0))
    index = COSArray()
    index.add(COSInteger.get(12))
    index.add(COSInteger.get(1))
    body.set_item("W", widths)
    body.set_item("Index", index)
    body.set_raw_data(b"\x07\x63")

    parser._decode_xref_stream_entries(body)  # noqa: SLF001

    entry = parser.get_xref_trailer_resolver().get_xref_table()[COSObjectKey(12, 0)]
    assert entry.type is XrefType.STREAM
    assert entry.offset == 0
    assert entry.compressed_index == -1


def test_wave583_handle_xref_stream_sets_encrypt_diagnostic_and_trailer() -> None:
    data = (
        b"9 0 obj\n"
        b"<< /Type /XRef /Size 0 /W [1 1 1] "
        b"/Encrypt << /Filter /Standard >> /Length 0 >>\n"
        b"stream\n\nendstream\nendobj\n"
    )
    parser = _parser(data)
    doc = COSDocument()
    parser._document = doc  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001
    parser.get_xref_trailer_resolver().begin_section(0)

    try:
        parser._handle_xref_stream_at(0)  # noqa: SLF001

        trailer = parser.get_trailer()
        assert parser.has_encrypted_xref_streams()
        assert isinstance(trailer, COSDictionary)
        assert isinstance(
            trailer.get_dictionary_object(COSName.ENCRYPT),  # type: ignore[attr-defined]
            COSDictionary,
        )
    finally:
        doc.close()


def test_wave583_resolve_stream_length_rejects_negative_direct_length() -> None:
    parser = _parser()
    stream = COSStream()
    stream.set_item("Length", COSInteger.get(-1))

    with pytest.raises(PDFParseError, match="negative"):
        parser._resolve_stream_length(stream)  # noqa: SLF001
