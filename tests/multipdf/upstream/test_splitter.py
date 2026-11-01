"""Ported from upstream ``SplitterTest.java`` (PDFBox 3.0 branch).

Upstream moved the splitter tests out of ``PDFMergerUtilityTest`` into
``SplitterTest`` (PDFBOX-6294). The tests that existed before that move
still live in ``tests/multipdf/upstream/test_pdf_merger_utility.py``; this
module holds ``testIllegalSplitting`` in its current form and the tests
added by PDFBOX-6283 (commit 22665c62).
"""

import pytest

from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)


def test_illegal_splitting() -> None:
    # IllegalArgumentException -> ValueError
    splitter = Splitter()
    with pytest.raises(ValueError) as ex:
        splitter.set_split_at_page(0)
    assert str(ex.value) == "Number of pages is smaller than one"
    with pytest.raises(ValueError) as ex:
        splitter.set_start_page(0)
    assert str(ex.value) == "Start page is smaller than one"
    with pytest.raises(ValueError) as ex:
        splitter.set_end_page(0)
    assert str(ex.value) == "End page is smaller than one"
    splitter.set_start_page(2)
    splitter.set_end_page(1)
    with PDDocument() as empty, pytest.raises(ValueError) as ex:
        splitter.split(empty)
    assert str(ex.value) == "End page is smaller than startPage"


def _add_link(from_page: PDPage, to_page: PDPage) -> None:
    destination = PDPageFitDestination()
    destination.set_page(to_page)
    link = PDAnnotationLink()
    link.set_destination(destination)
    link.set_rectangle(PDRectangle(10, 600, 100, 100))
    annotations = list(from_page.get_annotations())
    annotations.append(link)
    from_page.set_annotations(annotations)


def test_split_fixes_link_destinations_per_document() -> None:
    """Links must be fixed per split document: a link to a page in the same
    split document points to the imported page, a link to a page of another
    split document has no page."""
    with PDDocument() as document:
        pages = [PDPage() for _ in range(4)]
        for page in pages:
            document.add_page(page)
        _add_link(pages[0], pages[1])  # same split document
        _add_link(pages[0], pages[2])  # other split document
        _add_link(pages[2], pages[3])  # same split document

        splitter = Splitter()
        splitter.set_split_at_page(2)
        split = splitter.split(document)
        try:
            annotations0 = split[0].get_page(0).get_annotations()
            assert len(annotations0) == 2
            inside0 = annotations0[0].get_destination()
            outside0 = annotations0[1].get_destination()
            assert split[0].get_pages().index_of(inside0.get_page()) == 1
            assert outside0.get_page() is None

            annotations1 = split[1].get_page(0).get_annotations()
            assert len(annotations1) == 1
            inside1 = annotations1[0].get_destination()
            assert split[1].get_pages().index_of(inside1.get_page()) == 1
        finally:
            for dst_doc in split:
                dst_doc.close()


def test_split_start_page_beyond_last_page() -> None:
    with PDDocument() as document:
        document.add_page(PDPage())
        splitter = Splitter()
        splitter.set_start_page(5)
        assert splitter.split(document) == []


def test_split_closes_created_documents_on_failure() -> None:
    """All documents created so far must be closed when splitting fails, and
    the original exception must reach the caller."""
    created: list[PDDocument] = []

    class FailingSplitter(Splitter):
        def create_new_document(self) -> PDDocument:
            if len(created) == 2:
                raise OSError("simulated failure")
            new_document = super().create_new_document()
            created.append(new_document)
            return new_document

    splitter = FailingSplitter()
    with PDDocument() as source:
        for _ in range(3):
            source.add_page(PDPage())
        with pytest.raises(OSError) as ex:
            splitter.split(source)
        assert str(ex.value) == "simulated failure"
    assert len(created) == 2
    for new_document in created:
        assert new_document.get_document().is_closed()


def test_splitter_can_be_reused() -> None:
    splitter = Splitter()
    for page_count in (3, 2):
        with PDDocument() as source:
            for _ in range(page_count):
                source.add_page(PDPage())
            split = splitter.split(source)
            assert len(split) == page_count
            for dst_doc in split:
                assert dst_doc.get_number_of_pages() == 1
                dst_doc.close()
