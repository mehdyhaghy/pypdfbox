from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser


def _parser(data: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _build_pdf(
    objects: list[bytes],
    trailer: bytes = b"<< /Size 2 /Root 1 0 R >>",
) -> bytes:
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


def test_wave405_accessors_before_parse_and_knobs() -> None:
    parser = _parser(b"%PDF-1.4\n")

    assert parser.get_document() is None
    assert parser.get_xref_offset() == -1
    assert parser.get_trailer() is None
    assert parser.get_root() is None
    assert parser.get_password() is None
    assert parser.get_security_handler() is None
    assert not parser.has_encrypted_xref_streams()
    assert parser.is_lenient() is True

    parser.set_lenient(False)
    parser.set_password("secret")
    parser.set_eof_lookup_range(15)

    assert parser.is_lenient() is False
    assert parser.get_password() == "secret"
    assert parser.get_eof_lookup_range() > 15

    with pytest.raises(PDFParseError, match="before parse"):
        parser.get_pd_document()


def test_wave405_parse_pdf_header_sets_existing_document_version() -> None:
    parser = _parser(b"leading bytes\n%PDF-1.6\n")
    doc = COSDocument()
    try:
        parser._document = doc

        assert parser.parse_pdf_header() is True
        assert parser.get_document() is doc
        assert doc.get_version() == 1.6
    finally:
        doc.close()


def test_wave405_parse_pdf_header_returns_false_for_missing_header() -> None:
    assert _parser(b"not a pdf").parse_pdf_header() is False


def test_wave405_get_root_rejects_non_dictionary_and_id_uses_first_string() -> None:
    pdf = _build_pdf(
        [b"1 0 obj\n(plain root)\nendobj"],
        b"<< /Size 2 /Root 1 0 R /ID [(first-id) (second-id)] >>",
    )
    parser = _parser(pdf)
    doc = parser.parse()
    try:
        assert parser.get_root() is None
        assert parser.get_document_id() == b"first-id"
    finally:
        doc.close()


def test_wave405_direct_encrypt_dictionary_is_exposed_from_trailer() -> None:
    pdf = _build_pdf(
        [b"1 0 obj\n<< /Type /Catalog >>\nendobj"],
        b"<< /Size 2 /Root 1 0 R /Encrypt << /Filter /Standard /V 1 >> >>",
    )
    parser = _parser(pdf)
    doc = parser.parse()
    try:
        encrypt = parser.get_encryption_dictionary()
        assert isinstance(encrypt, COSDictionary)
        assert encrypt.get_name("Filter") == "Standard"
    finally:
        doc.close()


def test_wave405_get_pd_document_is_cached_after_parse() -> None:
    pdf = _build_pdf([b"1 0 obj\n<< /Type /Catalog >>\nendobj"])
    parser = _parser(pdf)
    doc = parser.parse()
    try:
        first = parser.get_pd_document()
        assert first is parser.get_pd_document()
        assert first.get_document() is doc
    finally:
        doc.close()


def test_wave405_linearization_records_hint_table_bytes() -> None:
    hint = b"HINTDATA"
    header = b"%PDF-1.4\n"
    hint_offset = 0
    while True:
        lin_dict = (
            b"1 0 obj\n<< /Linearized 1 /H [ "
            + str(hint_offset).encode("ascii")
            + b" "
            + str(len(hint)).encode("ascii")
            + b" ] >>\nendobj\n"
        )
        computed = len(header) + len(lin_dict)
        if computed == hint_offset:
            break
        hint_offset = computed

    out = bytearray(header + lin_dict + hint + b"\n")
    obj2_offset = len(out)
    out += b"2 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 3\n0000000000 65535 f \n"
    out += f"{len(b'%PDF-1.4\n'):010d} 00000 n \n".encode("ascii")
    out += f"{obj2_offset:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 3 /Root 2 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"

    parser = _parser(bytes(out))
    doc = parser.parse()
    try:
        assert parser.is_linearized() is True
        assert parser.get_linearization_dictionary() is not None
        assert parser.get_hint_table_bytes() == hint
    finally:
        doc.close()


def test_wave405_load_stream_recovers_missing_length_leniently() -> None:
    pdf = _build_pdf([b"1 0 obj\n<< /Type /Catalog >>\nstream\nabc\nendstream\nendobj"])
    parser = _parser(pdf)
    doc = parser.parse()
    try:
        stream = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
        assert isinstance(stream, COSStream)
        assert stream.get_raw_data() == b"abc"
    finally:
        doc.close()


def test_wave405_load_stream_recovers_malformed_length_leniently() -> None:
    pdf = _build_pdf(
        [b"1 0 obj\n<< /Type /Catalog /Length /Bad >>\nstream\nabc\nendstream\nendobj"]
    )
    parser = _parser(pdf)
    doc = parser.parse()
    try:
        stream = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
        assert isinstance(stream, COSStream)
        assert stream.get_raw_data() == b"abc"
    finally:
        doc.close()


def test_wave405_load_stream_rejects_missing_length_in_strict_mode() -> None:
    pdf = _build_pdf([b"1 0 obj\n<< /Type /Catalog >>\nstream\nabc\nendstream\nendobj"])
    parser = _parser(pdf)
    parser.set_lenient(False)
    doc = parser.parse()
    try:
        with pytest.raises(PDFParseError, match="stream missing or malformed /Length"):
            doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    finally:
        doc.close()


def test_wave405_xref_stream_entries_register_free_and_compressed_slots() -> None:
    body = b"\x00\x00\x00" + b"\x02\x05\x03"
    out = bytearray(b"%PDF-1.5\n")
    startxref = len(out)
    out += (
        b"9 0 obj\n"
        b"<< /Type /XRef /Size 8 /Index [ 6 2 ] /W [ 1 1 1 ] /Length "
        + str(len(body)).encode("ascii")
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
        b"startxref\n"
        + str(startxref).encode("ascii")
        + b"\n%%EOF"
    )

    parser = _parser(bytes(out))
    doc = parser.parse()
    try:
        table = parser.get_xref_trailer_resolver().get_xref_table()
        assert table[COSObjectKey(6, 0)].compressed_index == -1
        assert table[COSObjectKey(7, 0)].offset == 5
        assert table[COSObjectKey(7, 0)].compressed_index == 3
        assert not doc.has_object(COSObjectKey(6, 0))
        assert doc.has_object(COSObjectKey(7, 0))
    finally:
        doc.close()
