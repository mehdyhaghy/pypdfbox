from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSInteger, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser


def _minimal_pdf(*, trailer_extra: bytes = b"") -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    obj_offset = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 2\n"
    out += b"0000000000 65535 f \n"
    out += f"{obj_offset:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R"
    out += trailer_extra
    out += b" >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def _linearized_pdf_with_hint_bytes(hint: bytes = b"hint-table") -> bytes:
    offset = 0
    while True:
        out = bytearray(b"%PDF-1.5\n")
        lin_offset = len(out)
        out += (
            b"1 0 obj\n"
            + f"<< /Linearized 1 /L 0 /H [{offset} {len(hint)}] >>\n".encode(
                "ascii"
            )
            + b"endobj\n"
        )
        root_offset = len(out)
        out += b"2 0 obj\n<< /Type /Catalog >>\nendobj\n"
        hint_offset = len(out)
        out += hint
        xref_offset = len(out)
        out += b"\nxref\n0 3\n"
        out += b"0000000000 65535 f \n"
        out += f"{lin_offset:010d} 00000 n \n".encode("ascii")
        out += f"{root_offset:010d} 00000 n \n".encode("ascii")
        out += b"trailer\n<< /Size 3 /Root 2 0 R >>\n"
        out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
        if hint_offset == offset:
            return bytes(out)
        offset = hint_offset


def test_wave553_document_and_pd_document_accessors_are_stateful() -> None:
    parser = PDFParser(RandomAccessReadBuffer(_minimal_pdf()))

    assert parser.get_document() is None
    assert parser.get_xref_offset() == -1
    with pytest.raises(PDFParseError, match="before parse"):
        parser.get_pd_document()

    doc = parser.parse()
    try:
        assert parser.get_document() is doc
        assert parser.get_xref_offset() == _minimal_pdf().find(b"xref\n")
        assert parser.get_root() is not None
        assert parser.get_pd_document() is parser.get_pd_document()
    finally:
        doc.close()


def test_wave553_eof_lookup_range_ignores_too_small_values() -> None:
    parser = PDFParser(RandomAccessReadBuffer(_minimal_pdf()))

    original = parser.get_eof_lookup_range()
    parser.set_eof_lookup_range(15)
    assert parser.get_eof_lookup_range() == original

    parser.set_eof_lookup_range(16)
    assert parser.get_eof_lookup_range() == 16


def test_wave553_find_startxref_offset_reports_missing_marker_in_small_window() -> None:
    pdf = _minimal_pdf() + (b"\n%" * 20)
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.set_eof_lookup_range(16)

    with pytest.raises(PDFParseError, match="missing 'startxref'"):
        parser.find_startxref_offset()


def test_wave553_parse_pdf_header_sets_version_and_returns_boolean() -> None:
    parser = PDFParser(RandomAccessReadBuffer(b"noise\n%PDF-2.0\n"))
    doc = COSDocument()
    parser._document = doc  # noqa: SLF001

    try:
        assert parser.parse_pdf_header()
        assert parser._version == 2.0  # noqa: SLF001
        assert not PDFParser(RandomAccessReadBuffer(b"not a pdf")).parse_pdf_header()
    finally:
        doc.close()


def test_wave553_document_id_returns_first_trailer_id_string() -> None:
    pdf = _minimal_pdf(trailer_extra=b" /ID [(permanent-id) (changing-id)]")
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    doc = parser.parse()

    try:
        assert parser.get_document_id() == b"permanent-id"
        assert parser.get_encryption_dictionary() is None
    finally:
        doc.close()


def test_wave553_linearization_records_dictionary_and_hint_bytes() -> None:
    parser = PDFParser(RandomAccessReadBuffer(_linearized_pdf_with_hint_bytes()))
    doc = parser.parse()

    try:
        lin_dict = parser.get_linearization_dictionary()
        assert parser.is_linearized()
        assert lin_dict is not None
        assert isinstance(
            lin_dict.get_dictionary_object(COSName.get_pdf_name("Linearized")),
            COSInteger,
        )
        assert parser.get_hint_table_bytes() == b"hint-table"
    finally:
        doc.close()
