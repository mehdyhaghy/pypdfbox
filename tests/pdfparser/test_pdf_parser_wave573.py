from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefEntry, XrefType


def _parser(data: bytes = b"") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _xref_stream_pdf_with_bad_declared_offset() -> tuple[bytes, int]:
    out = bytearray(b"%PDF-1.5\n")
    xref_offset = len(out)
    out += (
        b"7 0 obj\n"
        b"<< /Type /XRef /Size 1 /Index [0 1] /W [1 1 1] /Length 3 >>\n"
        b"stream\n"
        b"\x01\x00\x00"
        b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_offset + 2).encode("ascii") + b"\n%%EOF"
    return bytes(out), xref_offset


def test_wave573_root_encryption_and_id_accessors_handle_absent_or_wrong_types() -> None:
    parser = _parser()

    assert parser.get_root() is None
    assert parser.get_encryption_dictionary() is None
    assert parser.get_document_id() is None

    trailer = COSDictionary()
    trailer.set_item("Root", COSInteger.get(1))
    trailer.set_item("Encrypt", COSInteger.get(2))
    ids = COSArray()
    ids.add(COSInteger.get(3))
    trailer.set_item("ID", ids)
    parser.get_xref_trailer_resolver().begin_section(0)
    parser.get_xref_trailer_resolver().set_trailer(trailer)

    assert parser.get_root() is None
    assert parser.get_encryption_dictionary() is None
    assert parser.get_document_id() is None


def test_wave573_parse_pdf_header_returns_false_without_clobbering_document() -> None:
    parser = _parser(b"not a pdf")
    doc = COSDocument()
    parser._document = doc  # noqa: SLF001
    parser._version = 1.7  # noqa: SLF001

    try:
        assert not parser.parse_pdf_header()
        assert parser._version == 1.7  # noqa: SLF001
        assert parser.get_document() is doc
    finally:
        doc.close()


def test_wave573_xref_shape_check_preserves_cursor_and_recognizes_xref_stream() -> None:
    pdf, xref_offset = _xref_stream_pdf_with_bad_declared_offset()
    parser = _parser(pdf)
    parser._cos_parser = COSParser(parser._src)  # noqa: SLF001
    parser._src.seek(len(pdf) - 5)  # noqa: SLF001

    assert parser._xref_section_starts_at(xref_offset)  # noqa: SLF001
    assert parser._src.get_position() == len(pdf) - 5  # noqa: SLF001
    assert not parser._xref_section_starts_at(-1)  # noqa: SLF001
    assert not parser._xref_section_starts_at(len(pdf))  # noqa: SLF001


def test_wave573_lenient_recovery_finds_nearby_xref_stream_offset() -> None:
    pdf, xref_offset = _xref_stream_pdf_with_bad_declared_offset()
    parser = _parser(pdf)
    parser._cos_parser = COSParser(parser._src)  # noqa: SLF001

    assert parser._recover_xref_offset_if_needed(xref_offset + 2) == xref_offset  # noqa: SLF001

    parser.set_lenient(False)
    assert parser._recover_xref_offset_if_needed(xref_offset + 2) == xref_offset + 2  # noqa: SLF001


def test_wave573_read_xref_entry_rejects_unknown_flag_after_parse() -> None:
    parser = _parser(b"0000000000 00000 q \n")
    parser.get_xref_trailer_resolver().begin_section(0)

    with pytest.raises(PDFParseError, match="unknown xref entry flag"):
        parser._read_xref_entry(3)  # noqa: SLF001


def test_wave573_resolve_dict_entry_returns_loaded_direct_and_skips_compressed() -> None:
    parser = _parser()
    parser.get_xref_trailer_resolver().begin_section(0)
    doc = parser._document = COSDocument()  # noqa: SLF001
    try:
        loaded_ref = doc.get_object_from_pool(COSObjectKey(4, 0))
        loaded_ref.set_object(COSInteger.get(44))
        compressed_ref = doc.get_object_from_pool(COSObjectKey(5, 0))
        trailer = COSDictionary()
        trailer.set_item("Loaded", loaded_ref)
        trailer.set_item("Compressed", compressed_ref)
        trailer.set_item("Direct", COSName.get_pdf_name("Value"))
        parser.get_xref_trailer_resolver().set_entry(
            COSObjectKey(5, 0),
            XrefEntry(type=XrefType.COMPRESSED, offset=9, compressed_index=0),
        )

        assert parser._resolve_dict_entry(  # noqa: SLF001
            trailer, COSName.get_pdf_name("Loaded")
        ) is COSInteger.get(44)
        assert parser._resolve_dict_entry(  # noqa: SLF001
            trailer, COSName.get_pdf_name("Direct")
        ) is COSName.get_pdf_name("Value")
        assert parser._resolve_dict_entry(  # noqa: SLF001
            trailer, COSName.get_pdf_name("Compressed")
        ) is None
        assert parser._resolve_dict_entry(  # noqa: SLF001
            trailer, COSName.get_pdf_name("Missing")
        ) is None
    finally:
        doc.close()
