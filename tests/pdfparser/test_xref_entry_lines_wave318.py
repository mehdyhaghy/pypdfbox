from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParser


def test_wave318_pdf_parser_accepts_compact_lf_xref_entries() -> None:
    out = bytearray(b"%PDF-1.4\n")
    catalog_offset = len(out)
    out += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    pages_offset = len(out)
    out += b"2 0 obj\n<< /Type /Pages /Count 0 >>\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 3\n"
    out += b"0000000000 65535 f\n"
    out += f"{catalog_offset:010d} 00000 n\n".encode("ascii")
    out += f"{pages_offset:010d} 00000 n\n".encode("ascii")
    out += b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"

    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    try:
        catalog = doc.get_catalog()
        assert isinstance(catalog, COSDictionary)
        assert catalog.get_name("Type") == "Catalog"
    finally:
        doc.close()


def test_wave318_cos_parser_accepts_compact_lf_xref_entries() -> None:
    pdf = (
        b"xref\n0 3\n"
        b"0000000000 65535 f\n"
        b"0000000017 00000 n\n"
        b"0000000089 00000 n\n"
        b"trailer << /Size 3 >>\n"
    )
    table: dict[COSObjectKey, int] = {}

    assert COSParser(RandomAccessReadBuffer(pdf)).parse_xref_table(0, table) is True
    assert table[COSObjectKey(0, 65535)] == -1
    assert table[COSObjectKey(1, 0)] == 17
    assert table[COSObjectKey(2, 0)] == 89
