from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObject, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser


def _cos_parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def _minimal_pdf_with_declared_startxref(declared_offset: int | None = None) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(out)
    if declared_offset is None:
        declared_offset = xref_offset
    out += b"xref\n0 2\n"
    out += b"0000000000 65535 f \n"
    out += b"0000000009 00000 n \n"
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(declared_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_wave544_cos_parser_header_predicates_preserve_position_and_defaults() -> None:
    parser = _cos_parser(b"noise\n%PDF-\n")
    parser.seek(3)

    assert parser.has_pdf_header()
    assert parser.position == 3
    assert parser.parse_pdf_header() == 1.4

    fdf_parser = _cos_parser(b"%FDF-\n")
    assert fdf_parser.has_fdf_header()
    assert fdf_parser.parse_fdf_header() == 1.0


def test_wave544_cos_parser_is_string_and_last_index_of_are_bounded() -> None:
    parser = _cos_parser(b"abcdef abc")
    parser.seek(3)

    assert parser.is_string("def")
    assert parser.position == 3
    assert not parser.is_string(b"abc")
    assert parser.last_index_of(b"abc", b"abc---abc---abc", 12) == 6
    assert parser.last_index_of(b"abc", b"abc---abc---abc", 5) == 0
    assert parser.last_index_of(b"xyz", b"abc---abc", 9) == -1


def test_wave544_cos_parser_parse_xref_table_populates_offsets_and_free_entries() -> None:
    data = (
        b"xref\n"
        b"0 3\n"
        b"0000000000 65535 f \n"
        b"0000000017 00000 n \n"
        b"0000000042 00002 n \n"
        b"trailer\n"
    )
    table: dict[COSObjectKey, int] = {COSObjectKey(1, 0): 999}

    assert _cos_parser(data).parse_xref_table(0, table)

    assert table[COSObjectKey(0, 65535)] == -1
    assert table[COSObjectKey(1, 0)] == 999
    assert table[COSObjectKey(2, 2)] == 42


def test_wave544_cos_parser_rebuild_trailer_finds_catalog_info_and_size() -> None:
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /Producer (pypdfbox) >>\nendobj\n"
        b"4 0 obj\n<< /ID [(abc) (def)] >>\nendobj\n"
    )
    trailer = _cos_parser(data).rebuild_trailer()

    root = trailer.get_item(COSName.ROOT)
    info = trailer.get_item(COSName.INFO)
    ids = trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
    size = trailer.get_dictionary_object(COSName.SIZE)

    assert isinstance(root, COSObject)
    assert root.get_object_number() == 1
    assert isinstance(info, COSObject)
    assert info.get_object_number() == 2
    assert ids is not None
    assert isinstance(size, COSInteger)
    assert size.value == 5


def test_wave544_pdf_parser_lenient_parse_recovers_nearby_xref_offset() -> None:
    correct_pdf = _minimal_pdf_with_declared_startxref()
    correct_offset = correct_pdf.find(b"xref\n")
    pdf = _minimal_pdf_with_declared_startxref(correct_offset + 1)
    parser = PDFParser(RandomAccessReadBuffer(pdf))

    doc = parser.parse()

    try:
        assert parser.get_xref_offset() == correct_offset
        assert parser.get_root() is not None
    finally:
        doc.close()


def test_wave544_pdf_parser_strict_parse_rejects_bad_startxref_offset() -> None:
    correct_offset = _minimal_pdf_with_declared_startxref().find(b"xref\n")
    parser = PDFParser(
        RandomAccessReadBuffer(
            _minimal_pdf_with_declared_startxref(correct_offset + 1)
        )
    )
    parser.set_lenient(False)

    with pytest.raises(PDFParseError, match="does not point to xref"):
        parser.parse()


def test_wave544_pdf_parser_root_ignores_non_dictionary_root() -> None:
    parser = PDFParser(RandomAccessReadBuffer(b""))
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, COSInteger.get(7))
    parser.get_xref_trailer_resolver().begin_section(0)
    parser.get_xref_trailer_resolver().set_trailer(trailer)

    assert parser.get_root() is None
