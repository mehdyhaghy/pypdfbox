from __future__ import annotations

import pytest

from pypdfbox.cos import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser


def _build_pdf(objects: list[bytes], trailer: bytes = b"<< /Size 2 /Root 1 0 R >>") -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
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
    out += b"trailer\n"
    out += trailer + b"\n"
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("ascii")
    out += b"%%EOF"
    return bytes(out)


def test_wave322_pdf_parser_rejects_direct_negative_stream_length() -> None:
    pdf = _build_pdf(
        [
            b"1 0 obj\n"
            b"<< /Length -1 >>\n"
            b"stream\n"
            b"ABCDE\n"
            b"endstream\n"
            b"endobj",
        ]
    )
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    try:
        stream_obj = doc.get_object_from_pool(COSObjectKey(1, 0))

        with pytest.raises(PDFParseError, match="stream /Length is negative: -1"):
            stream_obj.get_object()
    finally:
        doc.close()


def test_wave322_pdf_parser_rejects_indirect_negative_stream_length() -> None:
    pdf = _build_pdf(
        [
            b"1 0 obj\n"
            b"<< /Length 2 0 R >>\n"
            b"stream\n"
            b"ABCDE\n"
            b"endstream\n"
            b"endobj",
            b"2 0 obj\n-1\nendobj",
        ],
        trailer=b"<< /Size 3 /Root 1 0 R >>",
    )
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    try:
        stream_obj = doc.get_object_from_pool(COSObjectKey(1, 0))

        with pytest.raises(PDFParseError, match="stream /Length is negative: -1"):
            stream_obj.get_object()
    finally:
        doc.close()
