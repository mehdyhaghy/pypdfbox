"""Ported subset of upstream
``pdfbox/src/test/java/org/apache/pdfbox/pdfparser/COSParserTest.java``.

The upstream test exercises the brute-force / lenient recovery surface
of ``COSParser`` (rebuildTrailer, bfSearchForObjects, bfSearchForXRef,
parseXrefStream, parsePDFHeader). We translate the cases that have a
direct counterpart on our ``COSParser``.

JUnit5 → pytest mapping per the project's "Test Porting Conventions".

Skipped upstream cases:
- ``checkXRefStream`` exercises a Java ``RandomAccessFile`` against a
  shipped fixture corpus; we don't currently mirror those fixtures, so
  the equivalent case is covered by hand-written tests in
  ``test_cos_parser.py`` and ``test_cos_parser_recovery.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


# ---------- parsePDFHeader (translated from
# ``COSParserTest.testParsePDFHeader``) ----------


def test_parse_pdf_header_accepts_valid_magic() -> None:
    # JUnit: assertEquals(1.4, parser.parsePDFHeader())
    assert _parser(b"%PDF-1.4\n").parse_pdf_header() == 1.4


def test_parse_pdf_header_skips_garbage_before_magic() -> None:
    # JUnit: PDFBox tolerates leading garbage up to ~1KB.
    pdf = b"junk\n" * 50 + b"%PDF-1.7\n"
    assert _parser(pdf).parse_pdf_header() == 1.7


def test_parse_pdf_header_rejects_when_magic_absent() -> None:
    # JUnit: assertThrows(IOException, () -> parser.parsePDFHeader())
    with pytest.raises(PDFParseError):
        _parser(b"definitely not a PDF").parse_pdf_header()


# ---------- bfSearchForObjects (translated from
# ``COSParserTest.testBfSearchForObjects``) ----------


def test_bf_search_for_objects_finds_object_definitions() -> None:
    # JUnit: parser.bfSearchForObjects() returns a non-empty map when
    # the source contains 'n g obj' headers.
    pdf = b"%PDF-1.4\n1 0 obj\n42\nendobj\n2 0 obj\n(text)\nendobj\n%%EOF"
    objects = _parser(pdf).bf_search_for_objects()
    assert COSObjectKey(1, 0) in objects
    assert COSObjectKey(2, 0) in objects


def test_bf_search_for_objects_distinguishes_endobj() -> None:
    # JUnit: the brute-force scan must NOT mistake 'endobj' for 'obj'.
    pdf = b"%PDF-1.4\n7 0 obj\n42\nendobj\n%%EOF"
    objects = _parser(pdf).bf_search_for_objects()
    assert list(objects) == [COSObjectKey(7, 0)]


# ---------- bfSearchForXRef (translated from
# ``COSParserTest.testBfSearchForXRef``) ----------


def test_bf_search_for_xref_locates_xref_keyword() -> None:
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \n"
        b"trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n70\n%%EOF"
    )
    expected = pdf.find(b"xref\n0 2")
    assert _parser(pdf).bf_search_for_xref(expected + 100) == expected


def test_bf_search_for_xref_returns_minus_one_when_no_xref() -> None:
    pdf = b"%PDF-1.4\n1 0 obj\n42\nendobj\n%%EOF"
    assert _parser(pdf).bf_search_for_xref(0) == -1


# ---------- rebuildTrailer (translated from
# ``COSParserTest.testRebuildTrailer``) ----------


def test_rebuild_trailer_finds_root_via_catalog_type() -> None:
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\nendobj\n"
        b"%%EOF"
    )
    trailer = _parser(pdf, document=COSDocument()).rebuild_trailer()
    root = trailer.get_item(COSName.get_pdf_name("Root"))
    assert isinstance(root, COSObject)
    assert root.get_object_number() == 1


def test_rebuild_trailer_size_is_max_object_number_plus_one() -> None:
    pdf = (
        b"%PDF-1.4\n"
        b"3 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"%%EOF"
    )
    trailer = _parser(pdf, document=COSDocument()).rebuild_trailer()
    size = trailer.get_dictionary_object(COSName.get_pdf_name("Size"))
    assert isinstance(size, COSInteger)
    assert size.int_value() == 4


# ---------- parseXrefStream (translated from
# ``COSParserTest.testParseXrefStream``) ----------


def _xref_dict(
    w: list[int], index: list[int] | None = None, size: int | None = None
) -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XRef"))
    arr = COSArray()
    for v in w:
        arr.add(COSInteger.get(v))
    d.set_item(COSName.get_pdf_name("W"), arr)
    if index is not None:
        idx = COSArray()
        for v in index:
            idx.add(COSInteger.get(v))
        d.set_item(COSName.get_pdf_name("Index"), idx)
    if size is not None:
        d.set_item(COSName.get_pdf_name("Size"), COSInteger.get(size))
    return d


def test_parse_xref_stream_default_index() -> None:
    # JUnit: /Index defaults to [0 Size] when missing.
    p = _parser(b"")
    table = p.parse_xref_stream(_xref_dict([1, 2, 1], size=3))
    assert COSObjectKey(0, 0) in table
    assert COSObjectKey(1, 0) in table
    assert COSObjectKey(2, 0) in table


def test_parse_xref_stream_explicit_index() -> None:
    # JUnit: /Index [10 2 20 1] selects ranges (10..11) and (20).
    p = _parser(b"")
    table = p.parse_xref_stream(_xref_dict([1, 2, 1], index=[10, 2, 20, 1]))
    assert COSObjectKey(10, 0) in table
    assert COSObjectKey(11, 0) in table
    assert COSObjectKey(20, 0) in table


def test_parse_xref_stream_rejects_missing_w() -> None:
    # JUnit: assertThrows(IOException, ...) when /W is absent.
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Size"), COSInteger.get(1))
    with pytest.raises(PDFParseError):
        _parser(b"").parse_xref_stream(d)


# ---------- parseXrefTable (translated from
# ``COSParserTest.testParseXrefTable``) ----------


def test_parse_xref_table_reads_traditional_section() -> None:
    pdf = (
        b"xref\n0 2\n"
        b"0000000000 65535 f \n"
        b"0000000017 00000 n \n"
        b"trailer << /Size 2 >>\n"
    )
    table: dict = {}
    assert _parser(pdf).parse_xref_table(0, table) is True
    assert table[COSObjectKey(0, 65535)] == -1
    assert table[COSObjectKey(1, 0)] == 17


def test_parse_xref_table_returns_false_for_non_xref_keyword() -> None:
    # JUnit: parseXrefTable returns false if the offset doesn't start
    # with the 'xref' keyword.
    assert _parser(b"trailer << >>").parse_xref_table(0) is False
