from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSObjectKey, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParser
from pypdfbox.pdfparser.parse_error import PDFParseError


def _pack_xref_record(type_byte: int, field2: int, field3: int) -> bytes:
    return type_byte.to_bytes(1, "big") + field2.to_bytes(4, "big") + field3.to_bytes(
        2, "big"
    )


def test_prev_chain_uses_current_trailer_for_next_offset() -> None:
    out = bytearray(b"%PDF-1.4\n")

    obj1_off = len(out)
    out += b"1 0 obj\n(one)\nendobj\n"
    xref1_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 >>\nstartxref\n"
    out += str(xref1_off).encode("ascii") + b"\n%%EOF\n"

    obj2_off = len(out)
    out += b"2 0 obj\n(two)\nendobj\n"
    xref2_off = len(out)
    out += b"xref\n2 1\n"
    out += f"{obj2_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 3 /Prev "
    out += str(xref1_off).encode("ascii") + b" >>\nstartxref\n"
    out += str(xref2_off).encode("ascii") + b"\n%%EOF\n"

    obj3_off = len(out)
    out += b"3 0 obj\n(three)\nendobj\n"
    xref3_off = len(out)
    out += b"xref\n3 1\n"
    out += f"{obj3_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 4 /Prev "
    out += str(xref2_off).encode("ascii") + b" >>\nstartxref\n"
    out += str(xref3_off).encode("ascii") + b"\n%%EOF"

    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    try:
        for obj_num, expected in ((1, b"one"), (2, b"two"), (3, b"three")):
            body = doc.get_object_from_pool(COSObjectKey(obj_num, 0)).get_object()
            assert isinstance(body, COSString)
            assert body.get_bytes() == expected
    finally:
        doc.close()


def test_parse_object_stream_rejects_first_beyond_decoded_body() -> None:
    doc = COSDocument()
    pdf = (
        b"5 0 obj\n"
        b"<< /Type /ObjStm /N 1 /First 99 /Length 4 >>\n"
        b"stream\nDATA\nendstream\nendobj\n"
    )
    try:
        parser = COSParser(RandomAccessReadBuffer(pdf), document=doc)
        parser.parse_indirect_object_definition()

        with pytest.raises(PDFParseError, match="/First 99 exceeds decoded length"):
            COSParser(RandomAccessReadBuffer(b""), document=doc).parse_object_stream(5)
    finally:
        doc.close()


def test_compressed_object_loader_offset_outside_payload_resolves_null() -> None:
    out = bytearray(b"%PDF-1.5\n")
    objstm_body = b"7 99\n(one)"
    objstm_off = len(out)
    out += (
        b"1 0 obj\n<< /Type /ObjStm /N 1 /First 5 /Length "
        + str(len(objstm_body)).encode("ascii")
        + b" >>\nstream\n"
        + objstm_body
        + b"\nendstream\nendobj\n"
    )

    records = (
        _pack_xref_record(0, 0, 65535)
        + _pack_xref_record(1, objstm_off, 0)
        + _pack_xref_record(2, 1, 0)
        + _pack_xref_record(1, 0, 0)
    )
    xref_off = len(out)
    out += (
        b"2 0 obj\n<< /Type /XRef /Size 8 /Index [ 0 2 7 1 2 1 ]"
        b" /W [ 1 4 2 ] /Length "
        + str(len(records)).encode("ascii")
        + b" >>\nstream\n"
        + records
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"

    # Wave 1516: an in-header offset past the payload is a malformed
    # object-stream, which upstream ``COSParser.parseObjectStreamObject``
    # swallows in lenient mode (the default) and resolves to null — it does not
    # propagate. Validated against the live oracle (``header_offset_past_payload``
    # -> null on both sides). Lenient parsing is the default load mode.
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    try:
        obj7 = doc.get_object_from_pool(COSObjectKey(7, 0))
        assert obj7.get_object() is None
    finally:
        doc.close()
