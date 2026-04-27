"""Ported from upstream
``pdfbox/src/test/java/org/apache/pdfbox/multipdf/PDFCloneUtilityTest.java``
(PDFBox 3.0.x).

Two of the three upstream tests (``testClonePDFWithCosArrayStream2`` and
``testDirectIndirect``) depend on ``PDFMergerUtility`` and the
``PDOptionalContentProperties`` model wrappers, which are not yet ported.
We translate the first test (``testClonePDFWithCosArrayStream`` —
PDFBOX-2052) which directly exercises ``PDFCloneUtility``.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.multipdf import PDFCloneUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream


def test_clone_pdf_with_cos_array_stream() -> None:
    """Translation of upstream ``testClonePDFWithCosArrayStream``
    (PDFBOX-2052). Add two content streams to a page, clone the page
    dict into a fresh document, then confirm the clone exposes both
    content streams via ``get_content_streams``."""
    with PDDocument() as src_doc, PDDocument() as dst_doc:
        pd_page = PDPage()
        src_doc.add_page(pd_page)
        # Two appends: with the second one the /Contents entry must be
        # promoted to an array — exactly the shape that broke before
        # PDFBOX-2052 was fixed.
        PDPageContentStream(src_doc, pd_page, AppendMode.APPEND, True).close()
        PDPageContentStream(src_doc, pd_page, AppendMode.APPEND, True).close()
        cloner = PDFCloneUtility(dst_doc)
        assert cloner.get_destination() is dst_doc
        cloned_page_dict = cloner.clone_for_new_document(pd_page.get_cos_object())
        assert isinstance(cloned_page_dict, COSDictionary)
        cloned_page = PDPage(cloned_page_dict)
        streams = cloned_page.get_content_streams()
        assert len(streams) == 2
