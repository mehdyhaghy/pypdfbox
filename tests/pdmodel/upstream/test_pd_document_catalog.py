"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDDocumentCatalog.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.graphics.color import PDOutputIntent
from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange
from pypdfbox.pdmodel.pd_page_labels import PDPageLabels


def test_retrieve_page_labels() -> None:
    with PDDocument() as doc:
        for _ in range(12):
            doc.add_page(PDPage())
        labels = PDPageLabels(doc)
        labels.set_label_range(0, style=PDPageLabels.STYLE_DECIMAL, prefix="A")
        labels.set_label_range(3, style=PDPageLabels.STYLE_ROMAN_LOWER)
        labels.set_label_range(
            10,
            style=PDPageLabels.STYLE_ROMAN_UPPER,
            prefix="Appendix ",
        )
        doc.get_document_catalog().set_page_labels(labels)

        fetched = doc.get_document_catalog().get_page_labels()
        assert fetched is not None
        assert fetched.get_labels_by_page_indices() == [
            "A1",
            "A2",
            "A3",
            "i",
            "ii",
            "iii",
            "iv",
            "v",
            "vi",
            "vii",
            "Appendix I",
            "Appendix II",
        ]


def test_retrieve_page_labels_on_malformed_pdf() -> None:
    with PDDocument() as doc:
        for _ in range(4):
            doc.add_page(PDPage())
        nums = COSArray()
        nums.add(COSName.get_pdf_name("NotAnInt"))
        nums.add(COSDictionary())
        nums.add(COSInteger.get(-1))
        nums.add(COSDictionary())
        nums.add(COSInteger.get(1))
        nums.add(COSName.get_pdf_name("NotARange"))
        nums.add(COSInteger.get(2))
        valid = COSDictionary()
        valid.set_name(COSName.get_pdf_name("S"), PDPageLabelRange.STYLE_ROMAN_LOWER)
        nums.add(valid)
        tree = COSDictionary()
        tree.set_item(COSName.get_pdf_name("Nums"), nums)
        doc.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("PageLabels"), tree
        )

        with pytest.raises(OSError, match="index 1"):
            doc.get_document_catalog().get_page_labels()


def test_retrieve_number_of_pages() -> None:
    with PDDocument() as doc:
        assert doc.get_number_of_pages() == 0
        doc.add_page(PDPage())
        doc.add_page(PDPage())
        assert doc.get_number_of_pages() == 2


def test_handle_output_intents() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        first = PDOutputIntent()
        first.set_subtype(PDOutputIntent.GTS_PDFA1)
        second = PDOutputIntent()
        second.set_subtype(PDOutputIntent.GTS_PDFX)

        catalog.set_output_intents([first, second])

        fetched = catalog.get_output_intents()
        assert len(fetched) == 2
        assert fetched[0].get_cos_object() is first.get_cos_object()
        assert fetched[1].get_cos_object() is second.get_cos_object()


def test_handle_boolean_in_open_action() -> None:
    """``handleBooleanInOpenAction`` — malformed boolean must not crash."""
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("OpenAction"),
            COSBoolean.TRUE,
        )
        assert catalog.get_open_action() is None


def test_null_threads() -> None:
    """``testNullThreads`` — get_threads on a fresh document with no
    ``/Threads`` entry must return an empty list, not crash. Mirrors
    upstream's null-tolerant assertion (upstream returns ``null`` /
    we return an empty ``list`` per Python idiom — both are ``not
    truthy``)."""
    with PDDocument() as doc:
        threads = doc.get_document_catalog().get_threads()
        assert threads == []


# Even though every upstream test in this file targets later clusters,
# we keep at least one round-tripper for the methods cluster #1 *does*
# ship — language / page_layout / page_mode — so the upstream-suite has
# a passing case.
def test_catalog_string_round_trip_smoke() -> None:
    """Smoke parity test: language / layout / mode round-trip (covered by
    upstream's catalog accessors that lack standalone JUnit cases)."""
    with PDDocument() as doc:
        cat = doc.get_document_catalog()
        cat.set_language("en-US")
        cat.set_page_layout("OneColumn")
        cat.set_page_mode("UseOutlines")
        assert cat.get_language() == "en-US"
        assert cat.get_page_layout() == "OneColumn"
        assert cat.get_page_mode() == "UseOutlines"
