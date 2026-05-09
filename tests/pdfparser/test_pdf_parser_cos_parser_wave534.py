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


def _parser(data: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _minimal_pdf(objects: list[bytes], trailer: bytes) -> bytes:
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


def _xref_stream_dict(widths: list[int], size: int) -> COSDictionary:
    stream_dict = COSDictionary()
    w = COSArray()
    for width in widths:
        w.add(COSInteger.get(width))
    stream_dict.set_item("W", w)
    stream_dict.set_item("Size", COSInteger.get(size))
    return stream_dict


def test_wave534_pdf_parser_eof_lookup_range_controls_startxref_scan() -> None:
    pdf = _minimal_pdf(
        [b"1 0 obj\n<< /Type /Catalog >>\nendobj"],
        b"<< /Size 2 /Root 1 0 R >>",
    )
    parser = _parser(pdf + (b"\n%" * 40))
    parser.set_eof_lookup_range(16)

    with pytest.raises(PDFParseError, match="missing 'startxref'"):
        parser.find_startxref_offset()

    parser.set_eof_lookup_range(512)
    assert parser.find_startxref_offset() == pdf.find(b"xref\n")


def test_wave534_pdf_parser_get_pd_document_requires_parse_and_caches_wrapper() -> None:
    parser = _parser(
        _minimal_pdf(
            [b"1 0 obj\n<< /Type /Catalog >>\nendobj"],
            b"<< /Size 2 /Root 1 0 R >>",
        )
    )

    with pytest.raises(PDFParseError, match="before parse"):
        parser.get_pd_document()

    cos_doc = parser.parse()
    try:
        first = parser.get_pd_document()
        assert first is parser.get_pd_document()
        assert first.get_document() is cos_doc
    finally:
        cos_doc.close()


def test_wave534_pdf_parser_records_linearization_hint_bytes() -> None:
    hint_bytes = b"hint-table"
    hint_offset = 0
    linearization_object = b""
    while True:
        linearization_object = (
            b"1 0 obj\n<< /Linearized 1 /H ["
            + str(hint_offset).encode("ascii")
            + b" "
            + str(len(hint_bytes)).encode("ascii")
            + b"] >>\nendobj\n"
        )
        next_hint_offset = len(b"%PDF-1.4\n") + len(linearization_object)
        if next_hint_offset == hint_offset:
            break
        hint_offset = next_hint_offset
    out = bytearray(b"%PDF-1.4\n")
    out += linearization_object
    out += hint_bytes + b"\n"
    catalog_offset = len(out)
    out += b"2 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 3\n"
    out += b"0000000000 65535 f \n"
    out += b"0000000009 00000 n \n"
    out += f"{catalog_offset:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 3 /Root 2 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    parser = _parser(bytes(out))
    doc = parser.parse()

    try:
        assert parser.is_linearized()
        assert parser.get_linearization_dictionary() is not None
        assert parser.get_hint_table_bytes() == hint_bytes
    finally:
        doc.close()


def test_wave534_cos_parser_parse_xref_object_stream_reads_body() -> None:
    data = b"9 0 obj\n<< /Type /XRef /Length 3 >>\nstream\nabc\nendstream\nendobj\n"
    parser = COSParser(RandomAccessReadBuffer(data))

    stream = parser.parse_xref_object_stream(0)

    assert isinstance(stream, COSStream)
    assert stream.get_raw_data() == b"abc"
    assert stream.is_skip_encryption()


def test_wave534_cos_parser_parse_xref_stream_populates_existing_table() -> None:
    xref_table = {COSObjectKey(99, 0): 123}
    stream_dict = _xref_stream_dict([1, 2, 1], 0)
    index = COSArray()
    index.add(COSInteger.get(5))
    index.add(COSInteger.get(2))
    stream_dict.set_item("Index", index)

    parsed = COSParser(RandomAccessReadBuffer(b"")).parse_xref_stream(
        stream_dict, xref_table
    )

    assert parsed is xref_table
    assert parsed[COSObjectKey(99, 0)] == 123
    assert parsed[COSObjectKey(5, 0)] == 0
    assert parsed[COSObjectKey(6, 0)] == 4


def test_wave534_cos_parser_parse_object_stream_registers_all_objects() -> None:
    doc = COSDocument()
    try:
        obj_stream = COSStream(scratch_file=doc.scratch_file)
        obj_stream.set_item("Type", COSName.get_pdf_name("ObjStm"))
        obj_stream.set_item("N", COSInteger.get(2))
        obj_stream.set_item("First", COSInteger.get(8))
        obj_stream.set_raw_data(b"4 0 5 4\n(hi)/Name")
        doc.get_object_from_pool(COSObjectKey(8, 0)).set_object(obj_stream)

        parsed = COSParser(
            RandomAccessReadBuffer(b""), document=doc
        ).parse_object_stream(8)

        assert len(parsed) == 2
        assert doc.get_object_from_pool(COSObjectKey(4, 0)).get_object().get_bytes() == b"hi"
        assert doc.get_object_from_pool(
            COSObjectKey(5, 0)
        ).get_object() is COSName.get_pdf_name("Name")
    finally:
        doc.close()
