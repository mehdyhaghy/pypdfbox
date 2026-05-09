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


def _parser(data: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _build_pdf_with_xref_entry(entry: bytes) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    obj_offset = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n1 1\n" + entry + b"\n"
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    assert f"{obj_offset:010d}".encode("ascii") in entry
    return bytes(out)


def _xref_stream(widths: list[int], raw: bytes) -> COSStream:
    stream = COSStream()
    w = COSArray()
    for width in widths:
        w.add(COSInteger.get(width))
    stream.set_item("W", w)
    stream.set_raw_data(raw)
    return stream


def test_wave514_traditional_xref_rejects_unknown_entry_flag() -> None:
    pdf = _build_pdf_with_xref_entry(b"0000000009 00000 z ")

    with pytest.raises(PDFParseError, match="unknown xref entry flag"):
        _parser(pdf).parse()


def test_wave514_xref_stream_rejects_negative_width() -> None:
    parser = _parser(b"")
    parser.get_xref_trailer_resolver().begin_section(0)
    stream = _xref_stream([1, -1, 1], b"")
    stream.set_item("Size", COSInteger.get(1))

    with pytest.raises(PDFParseError, match="negative width"):
        parser._decode_xref_stream_entries(stream)  # noqa: SLF001


def test_wave514_xref_stream_rejects_odd_index_array() -> None:
    parser = _parser(b"")
    parser.get_xref_trailer_resolver().begin_section(0)
    stream = _xref_stream([1, 1, 1], b"")
    index = COSArray()
    index.add(COSInteger.get(0))
    stream.set_item("Index", index)

    with pytest.raises(PDFParseError, match="odd length"):
        parser._decode_xref_stream_entries(stream)  # noqa: SLF001


def test_wave514_stream_keyword_after_non_dictionary_object_raises() -> None:
    data = b"%PDF-1.4\n1 0 obj\n42\nstream\nabc\nendstream\nendobj\n"
    parser = _parser(data)
    doc = COSDocument()
    parser._document = doc  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001

    try:
        with pytest.raises(PDFParseError, match="stream object body is not a dictionary"):
            parser._load_indirect_object_at(9, COSObject(1, 0))  # noqa: SLF001
    finally:
        doc.close()


def test_wave514_compressed_object_loader_parses_direct_object() -> None:
    parser = _parser(b"")
    doc = COSDocument()
    parser._document = doc  # noqa: SLF001
    try:
        obj_stream = COSStream(scratch_file=doc.scratch_file)
        obj_stream.set_item("Type", COSName.get_pdf_name("ObjStm"))
        obj_stream.set_item("N", COSInteger.get(1))
        obj_stream.set_item("First", COSInteger.get(4))
        obj_stream.set_raw_data(b"4 0\n99")
        doc.get_object_from_pool(COSObjectKey(8, 0)).set_object(obj_stream)

        loaded = parser._load_compressed_object(8, 0, COSObject(4, 0))  # noqa: SLF001

        assert loaded is COSInteger.get(99)
    finally:
        doc.close()
