"""Tests ported from PDFBox 3.0 ``PDFCloneUtilityTest`` (extended slice).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/multipdf/PDFCloneUtilityTest.java``
on the apache/pdfbox 3.0 branch.

The ``testClonePDFWithCosArrayStream`` and ``testDirectIndirect``
methods are in :mod:`tests.multipdf.upstream.test_pdf_clone_utility`.
This file adds ``testClonePDFWithCosArrayStream2``: the "broader"
PDFBOX-2052 round-trip that saves both source and merged documents to
disk and reloads them to confirm the writer produces legitimate PDFs.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream


def test_clone_pdf_with_cos_array_stream2(tmp_path: Path) -> None:
    """Port of ``PDFCloneUtilityTest#testClonePDFWithCosArrayStream2``.

    Mirrors the broader PDFBOX-2052 regression: stack three appended
    content streams on a single page, save the source, merge into a
    fresh document, save the merged copy, then reload both and verify
    they remain valid 1-page PDFs.
    """
    clone_src = tmp_path / "clone-src.pdf"
    clone_dst = tmp_path / "clone-dst.pdf"

    with PDDocument() as src_doc:
        pd_page = PDPage()
        src_doc.add_page(pd_page)

        with PDPageContentStream(src_doc, pd_page, AppendMode.APPEND, False) as cs1:
            cs1.set_non_stroking_color_rgb_int(0, 0, 0)  # black
            cs1.add_rect(100, 600, 300, 100)
            cs1.fill()
        with PDPageContentStream(src_doc, pd_page, AppendMode.APPEND, False) as cs2:
            cs2.set_non_stroking_color_rgb_int(255, 0, 0)  # red
            cs2.add_rect(100, 500, 300, 100)
            cs2.fill()
        with PDPageContentStream(src_doc, pd_page, AppendMode.APPEND, False) as cs3:
            cs3.set_non_stroking_color_rgb_int(255, 255, 0)  # yellow
            cs3.add_rect(100, 400, 300, 100)
            cs3.fill()

        src_doc.save(str(clone_src))
        merger = PDFMergerUtility()
        with PDDocument() as dst_doc:
            # The append goes through PDFCloneUtility.clone_for_new_document
            # — would crash before the PDFBOX-2052 fix.
            merger.append_document(dst_doc, src_doc)
            dst_doc.save(str(clone_dst))

    # Reload both files (positional path; with-and-without password
    # variants upstream exists to exercise the no-password ``loadPDF``
    # overload — we collapse those to one each).
    with PDDocument.load(str(clone_src)) as doc:
        assert doc.get_number_of_pages() == 1
    with PDDocument.load(str(clone_src), None) as doc:
        assert doc.get_number_of_pages() == 1
    with PDDocument.load(str(clone_dst)) as doc:
        assert doc.get_number_of_pages() == 1
    with PDDocument.load(str(clone_dst), None) as doc:
        assert doc.get_number_of_pages() == 1
