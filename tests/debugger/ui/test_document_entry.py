"""Hand-written tests for ``pypdfbox.debugger.ui.DocumentEntry``."""

from pypdfbox.debugger.ui import DocumentEntry, PageEntry
from pypdfbox.pdmodel import PDDocument, PDPage


def test_basic_two_pages() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    entry = DocumentEntry(doc, "sample.pdf")
    try:
        assert str(entry) == "sample.pdf"
        assert entry.get_page_count() == 2

        first = entry.get_page(0)
        second = entry.get_page(1)
        assert isinstance(first, PageEntry)
        assert isinstance(second, PageEntry)
        assert first.get_page_num() == 1
        assert second.get_page_num() == 2

        # index_of is the inverse of page-num.
        assert entry.index_of(first) == 0
        assert entry.index_of(second) == 1
    finally:
        doc.close()


def test_empty_document_has_zero_pages() -> None:
    doc = PDDocument()
    try:
        entry = DocumentEntry(doc, "empty.pdf")
        assert entry.get_page_count() == 0
    finally:
        doc.close()
