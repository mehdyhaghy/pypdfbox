from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def _objstm_source(body: bytes, *, n: int, first: int) -> bytes:
    return (
        b"1 0 obj\n"
        b"<< /Type /ObjStm /N "
        + str(n).encode("ascii")
        + b" /First "
        + str(first).encode("ascii")
        + b" /Length "
        + str(len(body)).encode("ascii")
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
    )


def test_wave379_parse_cos_string_rejects_eof() -> None:
    with pytest.raises(PDFParseError, match="expected COS string"):
        _parser(b"   ").parse_cos_string()


def test_wave379_stream_object_body_must_be_dictionary() -> None:
    parser = _parser(b"5 0 obj 123 stream\nABCDE\nendstream endobj")

    with pytest.raises(PDFParseError, match="stream object body is not a dictionary"):
        parser.parse_indirect_object_definition()


def test_wave379_stream_keyword_without_eol_rewinds_to_body_start() -> None:
    parser = _parser(b"5 0 obj << /Length 5 >> stream(abc)endstream endobj")

    stream = parser.parse_indirect_object_definition().get_object()

    assert isinstance(stream, COSStream)
    assert stream.get_raw_data() == b"(abc)"


def test_wave379_parse_xref_object_stream_rejects_scalar_body() -> None:
    parser = _parser(b"7 0 obj\n42\nendobj\n")

    with pytest.raises(PDFParseError, match="body is not a dictionary"):
        parser.parse_xref_object_stream(0)


def test_wave379_parse_xref_table_returns_false_on_malformed_entry() -> None:
    parser = _parser(b"xref\n0 1\nnot-an-entry\ntrailer\n<< /Size 1 >>\n")

    assert parser.parse_xref_table(0) is False


def test_wave379_bf_search_for_xref_falls_back_to_xref_stream_object() -> None:
    prefix = b"%PDF-1.5\n% no traditional table here\n"
    xref_offset = len(prefix)
    pdf = (
        prefix
        + b"9 0 obj\n<< /Type /XRef /Size 1 /W [ 1 1 1 ] /Length 3 >>\n"
        + b"stream\n\x00\x00\x00\nendstream\nendobj\n"
        + b"startxref\n999\n%%EOF"
    )

    assert _parser(pdf).bf_search_for_xref(999) == xref_offset


def test_wave379_rebuild_trailer_copies_encrypt_reference() -> None:
    doc = COSDocument()
    parser = _parser(
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /Producer (pypdfbox) >>\nendobj\n"
        b"3 0 obj\n<< /Encrypt 4 0 R >>\nendobj\n",
        document=doc,
    )

    try:
        trailer = parser.rebuild_trailer()
        root = trailer.get_item("Root")
        info = trailer.get_item("Info")
        encrypt = trailer.get_item("Encrypt")

        assert isinstance(root, COSObject)
        assert root.object_number == 1
        assert isinstance(info, COSObject)
        assert info.object_number == 2
        assert isinstance(encrypt, COSObject)
        assert encrypt.object_number == 4
        assert trailer.get_int("Size") == 4
    finally:
        doc.close()


def test_wave379_parse_object_stream_rejects_negative_first() -> None:
    # Wave 1516: ``/First`` is read via ``getInt`` (upstream
    # ``PDFObjectStreamParser`` parity), whose -1 sentinel makes a literal
    # ``/First -1`` indistinguishable from a MISSING ``/First`` — both surface
    # the same "entry missing" error PDFBox raises.
    doc = COSDocument()
    parser = _parser(_objstm_source(b"", n=0, first=-1), document=doc)

    try:
        parser.parse_indirect_object_definition()
        with pytest.raises(PDFParseError, match="/First entry missing"):
            _parser(b"", document=doc).parse_object_stream(1)
    finally:
        doc.close()


def test_wave379_parse_object_stream_tolerates_inflated_n() -> None:
    # Wave 1503: aligned with upstream ``PDFObjectStreamParser`` (Java
    # ``privateReadObjectOffsets``), which reads at most /N pairs but breaks as
    # soon as the cursor reaches the /First boundary. An /N larger than the
    # actual number of header pairs (here /N=2 with a single ``10 0`` pair) is
    # bounded by the header region rather than raising — the lone member (obj
    # 10) still parses. The previous wave-379 pin asserted an over-strict
    # "header truncated" reject that upstream does not produce.
    doc = COSDocument()
    body = b"10 0 (x)"
    parser = _parser(_objstm_source(body, n=2, first=len(b"10 0 ")), document=doc)

    try:
        parser.parse_indirect_object_definition()
        parsed = _parser(b"", document=doc).parse_object_stream(1)

        assert len(parsed) == 1
        assert isinstance(parsed[0], COSString)
        assert parsed[0].get_string() == "x"
        assert doc.has_object(COSObjectKey(10, 0))
    finally:
        doc.close()


def test_wave379_parse_object_stream_rejects_payload_offset_outside_body() -> None:
    doc = COSDocument()
    body = b"10 99 (x)"
    parser = _parser(_objstm_source(body, n=1, first=len(b"10 99 ")), document=doc)

    try:
        parser.parse_indirect_object_definition()
        with pytest.raises(PDFParseError, match="outside payload length"):
            _parser(b"", document=doc).parse_object_stream(1)
    finally:
        doc.close()


def test_wave379_parse_object_stream_registers_zero_generation_objects() -> None:
    doc = COSDocument()
    body = b"12 0 42"
    parser = _parser(_objstm_source(body, n=1, first=len(b"12 0 ")), document=doc)

    try:
        parser.parse_indirect_object_definition()
        parsed = _parser(b"", document=doc).parse_object_stream(1)

        assert parsed == [COSInteger.get(42)]
        assert doc.has_object(COSObjectKey(12, 0))
        pooled = doc.get_object_from_pool(COSObjectKey(12, 0)).get_object()
        assert pooled == COSInteger.get(42)
        objstm = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
        assert objstm.get_name(COSName.TYPE) == "ObjStm"  # type: ignore[attr-defined]
    finally:
        doc.close()
