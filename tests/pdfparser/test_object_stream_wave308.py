from __future__ import annotations

from pypdfbox.cos import COSDocument, COSObjectKey, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParser


def _pack_record(type_byte: int, field2: int, field3: int) -> bytes:
    return (
        type_byte.to_bytes(1, "big")
        + field2.to_bytes(4, "big")
        + field3.to_bytes(2, "big")
    )


def test_wave308_cos_parser_tolerates_non_objstm_container_type() -> None:
    # Wave 1516: upstream ``PDFObjectStreamParser`` validates only ``/N`` and
    # ``/First`` — it never inspects ``/Type``. A container advertising a
    # non-``/ObjStm`` ``/Type`` but carrying a well-formed header therefore
    # decodes its members rather than raising (validated against the live
    # oracle: ``type_wrong`` / ``type_missing`` resolve at parity).
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

    parsed = COSParser(
        RandomAccessReadBuffer(b""), document=doc
    ).parse_object_stream(1)
    assert len(parsed) == 1
    assert isinstance(parsed[0], COSString)
    assert parsed[0].get_bytes() == b"payload"
    assert doc.has_object(COSObjectKey(5, 0))
    doc.close()


def test_wave308_lazy_compressed_loader_tolerates_non_objstm_container_type() -> None:
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

    # Wave 1516: the lazy compressed loader no longer rejects a non-``/ObjStm``
    # ``/Type`` (upstream checks only ``/N`` / ``/First``) — the member resolves.
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    resolved = doc.get_object_from_pool(COSObjectKey(5, 0)).get_object()
    assert isinstance(resolved, COSString)
    assert resolved.get_bytes() == b"payload"
    doc.close()
