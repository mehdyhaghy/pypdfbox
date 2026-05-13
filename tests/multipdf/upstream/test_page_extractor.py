"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/multipdf/PageExtractorTest.java``
(PDFBox 3.0).

Upstream loads ``src/test/resources/input/cweb.pdf`` (a 10-page PDF) and
asserts page counts after various extraction calls. We don't ship the
``cweb.pdf`` fixture, so we synthesise an equivalent 10-page document on
the fly — the assertions translate verbatim.
"""

from __future__ import annotations

import contextlib

from pypdfbox import PDDocument, PDPage
from pypdfbox.multipdf import PageExtractor


def _build_10_page_doc() -> PDDocument:
    doc = PDDocument()
    for _ in range(10):
        doc.add_page(PDPage())
    return doc


def _close_doc(doc: PDDocument | None) -> None:
    """Mirrors upstream ``closeDoc`` — swallows close errors."""
    if doc is not None:
        with contextlib.suppress(Exception):
            doc.close()


def test_extract() -> None:
    """Test of extract method, of class
    org.apache.pdfbox.util.PageExtractor."""
    source_pdf: PDDocument | None = None
    result: PDDocument | None = None
    try:
        source_pdf = _build_10_page_doc()

        # this should work for most users
        instance = PageExtractor(source_pdf)
        result = instance.extract()
        assert result.get_number_of_pages() == source_pdf.get_number_of_pages()
        _close_doc(result)

        instance = PageExtractor(source_pdf, 1, 1)
        result = instance.extract()
        assert result.get_number_of_pages() == 1
        _close_doc(result)

        instance = PageExtractor(source_pdf, 1, 5)
        result = instance.extract()
        assert result.get_number_of_pages() == 5
        _close_doc(result)

        instance = PageExtractor(source_pdf, 5, 10)
        result = instance.extract()
        assert result.get_number_of_pages() == 6
        _close_doc(result)

        instance = PageExtractor(source_pdf, 2, 1)
        result = instance.extract()
        assert result.get_number_of_pages() == 0
        _close_doc(result)
    finally:
        _close_doc(source_pdf)
        _close_doc(result)
