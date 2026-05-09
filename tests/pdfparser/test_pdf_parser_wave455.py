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


def _parser(data: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _build_pdf(objects: list[bytes], trailer: bytes) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for body in objects:
        offsets.append(len(out))
        out += body
        if not body.endswith(b"\n"):
            out += b"\n"
    xref_offset = len(out)
    out += b"xref\n"
    out += f"0 {len(offsets)}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n" + trailer + b"\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def _xref_stream(widths: list[int], raw: bytes) -> COSStream:
    stream = COSStream()
    w = COSArray()
    for width in widths:
        w.add(COSInteger.get(width))
    stream.set_item("W", w)
    stream.set_raw_data(raw)
    return stream


def test_wave455_prev_cycle_stops_after_first_section() -> None:
    out = bytearray(b"%PDF-1.4\n")
    obj_offset = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj_offset:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 2 /Root 1 0 R /Prev "
        + str(xref_offset).encode("ascii")
        + b" >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF"
    )

    parser = _parser(bytes(out))
    doc = parser.parse()
    try:
        resolver = parser.get_xref_trailer_resolver()
        assert resolver.section_count() == 1
        assert resolver.visited_offsets() == {xref_offset}
        assert doc.has_object(COSObjectKey(1, 0))
    finally:
        doc.close()


def test_wave455_find_startxref_honors_configured_scan_window() -> None:
    pdf = _build_pdf(
        [b"1 0 obj\n<< /Type /Catalog >>\nendobj"],
        b"<< /Size 2 /Root 1 0 R >>",
    )
    parser = _parser(pdf)
    parser.set_eof_lookup_range(16)

    with pytest.raises(PDFParseError, match="missing 'startxref'"):
        parser.find_startxref_offset()


def test_wave455_xref_section_probe_preserves_cursor_on_malformed_object() -> None:
    pdf = b"%PDF-1.5\n9 0 obj\n42\nendobj\n"
    parser = _parser(pdf)
    parser._document = COSDocument()
    parser._cos_parser = COSParser(parser._src, document=parser._document)
    parser._src.seek(len(pdf))
    try:
        assert parser._xref_section_starts_at(len(b"%PDF-1.5\n")) is False
        assert parser._src.get_position() == len(pdf)
    finally:
        parser._document.close()


def test_wave455_decode_xref_stream_defaults_generation_and_null_types() -> None:
    parser = _parser(b"")
    parser.get_xref_trailer_resolver().begin_section(0)
    stream = _xref_stream([1, 1, 0], b"\x01\x09\x08\x07")
    index = COSArray()
    index.add(COSInteger.get(4))
    index.add(COSInteger.get(2))
    stream.set_item("Index", index)

    parser._decode_xref_stream_entries(stream)

    table = parser.get_xref_trailer_resolver().get_xref_table()
    assert table[COSObjectKey(4, 0)].type is XrefType.STREAM
    assert table[COSObjectKey(4, 0)].offset == 9
    assert table[COSObjectKey(5, 0)].compressed_index == -1


def test_wave455_decode_xref_stream_rejects_truncated_body() -> None:
    parser = _parser(b"")
    parser.get_xref_trailer_resolver().begin_section(0)
    stream = _xref_stream([1, 1, 1], b"\x01\x00")
    stream.set_item("Size", COSInteger.get(1))

    with pytest.raises(PDFParseError, match="body truncated"):
        parser._decode_xref_stream_entries(stream)


def test_wave455_load_compressed_object_rejects_out_of_range_index() -> None:
    doc = COSDocument()
    try:
        objstm = COSStream(scratch_file=doc.scratch_file)
        objstm.set_item("Type", COSName.get_pdf_name("ObjStm"))
        objstm.set_item("N", COSInteger.get(1))
        objstm.set_item("First", COSInteger.get(5))
        objstm.set_raw_data(b"10 0\n42")
        doc.get_object_from_pool(COSObjectKey(7, 0)).set_object(objstm)

        parser = _parser(b"")
        parser._document = doc

        with pytest.raises(PDFParseError, match="out of range"):
            parser._load_compressed_object(7, 1, COSObject(10, 0))
    finally:
        doc.close()
