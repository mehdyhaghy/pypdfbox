"""Ported from upstream
``pdfbox/src/test/java/org/apache/pdfbox/multipdf/PDFCloneUtilityTest.java``
(PDFBox 3.0.x).

Two of the three upstream tests are translated here. The third
(``testClonePDFWithCosArrayStream2``) saves to disk and re-reads with
``Loader`` purely to assert that the output is a valid 1-page PDF; the
behaviour it covers is already exercised by ``testClonePDFWithCosArrayStream``
plus the merger round-trip suite, so it is intentionally skipped to
avoid scratch-file churn during the test run.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSName, COSObject
from pypdfbox.loader import Loader
from pypdfbox.multipdf import PDFCloneUtility, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
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


def test_direct_indirect() -> None:
    """Translation of upstream ``testDirectIndirect`` (PDFBOX-4814).

    Merges two documents where the source's ``/OCProperties`` entry is a
    direct ``COSDictionary`` and the destination's ``/OCProperties``
    entry — after a save / reload round-trip — is an indirect
    ``COSObject``. The clone-merge path must transparently dereference
    the indirect side so the merge succeeds and both pages survive."""
    oc_props_key = COSName.get_pdf_name("OCProperties")

    with PDDocument() as doc1:
        doc1.add_page(PDPage())
        doc1.get_document_catalog().set_oc_properties(PDOptionalContentProperties())

        # Round-trip doc1 through bytes so its /OCProperties is promoted
        # to an indirect object on the reloaded copy.
        baos = io.BytesIO()
        doc1.save(baos)

        cos_doc = Loader.load_pdf(baos.getvalue())
        with PDDocument(cos_doc) as doc2:
            merger = PDFMergerUtility()

            # Upstream's invariant: OCProperties is direct on doc1, indirect on doc2.
            doc1_oc = doc1.get_document_catalog().get_cos_object().get_item(oc_props_key)
            doc2_oc = doc2.get_document_catalog().get_cos_object().get_item(oc_props_key)
            assert isinstance(doc1_oc, COSDictionary)
            assert isinstance(doc2_oc, COSObject)

            merger.append_document(doc2, doc1)
            assert doc2.get_number_of_pages() == 2
