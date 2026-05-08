from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParser
from pypdfbox.pdfparser.parse_error import PDFParseError


def _pack_record(type_byte: int, field2: int, field3: int) -> bytes:
    return (
        type_byte.to_bytes(1, "big")
        + field2.to_bytes(4, "big")
        + field3.to_bytes(2, "big")
    )


def test_wave308_cos_parser_rejects_non_objstm_container() -> None:
    body = b"5 0 (payload) "
    doc = COSDocument()
    source = (
        b"1 0 obj\n"
        b"<< /Type /Metadata /N 1 /First 4 /Length "
        + str(len(body)).encode("ascii")
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
    )
    parser = COSParser(RandomAccessReadBuffer(source), document=doc)
    parser.parse_indirect_object_definition()

    with pytest.raises(PDFParseError, match="/Type /ObjStm"):
        COSParser(RandomAccessReadBuffer(b""), document=doc).parse_object_stream(1)


def test_wave308_lazy_compressed_loader_rejects_non_objstm_container() -> None:
    out = bytearray(b"%PDF-1.5\n")
    body = b"5 0 (payload) "
    stream_offset = len(out)
    out += (
        b"1 0 obj\n"
        b"<< /Type /Metadata /N 1 /First 4 /Length "
        + str(len(body)).encode("ascii")
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
    )
    records = (
        _pack_record(0, 0, 65535)
        + _pack_record(1, stream_offset, 0)
        + _pack_record(2, 1, 0)
        + _pack_record(1, 0, 0)
    )
    xref_offset = len(out)
    out += (
        b"2 0 obj\n"
        b"<< /Type /XRef /Size 6 /Index [ 0 2 5 1 2 1 ] "
        b"/W [ 1 4 2 ] /Length "
        + str(len(records)).encode("ascii")
        + b" >>\nstream\n"
        + records
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"

    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    with pytest.raises(PDFParseError, match="/Type /ObjStm"):
        doc.get_object_from_pool(COSObjectKey(5, 0)).get_object()
