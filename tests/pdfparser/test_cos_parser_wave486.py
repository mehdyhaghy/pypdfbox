from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def test_wave486_parse_indirect_stream_accepts_direct_length_and_bare_cr() -> None:
    parser = _parser(b"7 0 obj\n<< /Length 4 >>\nstream\rdata\rendstream\nendobj\n")

    obj = parser.parse_indirect_object_definition()
    stream = obj.get_object()

    assert stream.get_int("Length") == 4
    assert stream.get_raw_data() == b"data"


def test_wave486_parse_indirect_stream_rejects_negative_length() -> None:
    parser = _parser(b"7 0 obj\n<< /Length -1 >>\nstream\ndata\nendstream\nendobj\n")

    with pytest.raises(PDFParseError, match="negative"):
        parser.parse_indirect_object_definition()


def test_wave486_parse_indirect_object_rejects_stream_after_non_dictionary() -> None:
    parser = _parser(b"7 0 obj\n42\nstream\ndata\nendstream\nendobj\n")

    with pytest.raises(PDFParseError, match="not a dictionary"):
        parser.parse_indirect_object_definition()


def test_wave486_parse_xref_table_records_normal_and_free_entries() -> None:
    table: dict[COSObjectKey, int] = {COSObjectKey(1, 0): 1234}
    parser = _parser(
        b"xref\n"
        b"0 3\n"
        b"0000000000 65535 f \n"
        b"0000000017 00000 n \n"
        b"0000000029 00002 n \n"
        b"trailer\n<< /Size 3 >>\n"
    )

    assert parser.parse_xref_table(0, table)
    assert table[COSObjectKey(0, 65535)] == -1
    assert table[COSObjectKey(1, 0)] == 1234
    assert table[COSObjectKey(2, 2)] == 29


def test_wave486_parse_xref_object_stream_nonstandalone_allows_missing_xref_type() -> None:
    parser = _parser(
        b"9 0 obj\n<< /Size 1 /W [1 1 1] /Length 3 >>\nstream\nabc\nendstream\nendobj\n"
    )

    stream = parser.parse_xref_object_stream(0, is_standalone=False)

    assert stream.get_raw_data() == b"abc"
    assert stream.is_skip_encryption()


def test_wave486_parse_pdf_header_rejects_malformed_version() -> None:
    # Upstream raises only in STRICT mode; lenient defaults the version to 1.7.
    p = _parser(b"%PDF-not-a-version\n")
    p.set_lenient(False)
    with pytest.raises(PDFParseError, match="Error getting header version"):
        p.parse_pdf_header()
    assert _parser(b"%PDF-not-a-version\n").parse_pdf_header() == 1.7


def test_wave486_parse_object_stream_registers_contained_objects() -> None:
    doc = COSDocument()
    try:
        body = b"11 0 12 3 42 /Name"
        source = (
            b"5 0 obj\n"
            b"<< /Type /ObjStm /N 2 /First 10 /Length "
            + str(len(body)).encode("ascii")
            + b" >>\nstream\n"
            + body
            + b"\nendstream\nendobj\n"
        )
        _parser(source, document=doc).parse_indirect_object_definition()

        parsed = _parser(b"", document=doc).parse_object_stream(5)

        assert [item.get_object() if hasattr(item, "get_object") else item for item in parsed]
        assert doc.get_object_from_pool(COSObjectKey(11, 0)).get_object() is COSInteger.get(42)
        name = doc.get_object_from_pool(COSObjectKey(12, 0)).get_object()
        assert name is COSName.get_pdf_name("Name")
    finally:
        doc.close()


def test_wave486_rebuild_trailer_copies_encrypt_reference() -> None:
    trailer = _parser(
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /Encrypt 8 0 R >>\nendobj\n"
    ).rebuild_trailer()

    encrypt = trailer.get_item("Encrypt")
    assert encrypt.get_object_number() == 8  # type: ignore[attr-defined]
