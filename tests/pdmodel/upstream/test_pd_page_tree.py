"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDPageTree.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage


# ``indexOfPageFromOutlineDestination`` — outline/destination primitives
# are covered synthetically in cluster #7, but the upstream port still
# needs the ``with_outline.pdf`` fixture.
@pytest.mark.skip(reason="needs with_outline.pdf fixture")
def test_index_of_page_from_outline_destination() -> None:  # pragma: no cover
    pass


# ``positiveSingleLevel`` and ``positiveMultipleLevel`` rely on fixture PDFs.
# The ``PDPageTree.indexOf`` mechanic is exercised by our hand-written
# ``test_pd_page_tree.py``; we'd duplicate it without the fixtures, so skip
# rather than synthesise.
@pytest.mark.skip(reason="needs with_outline.pdf fixture")
def test_positive_single_level() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(reason="needs page_tree_multiple_levels.pdf fixture")
def test_positive_multiple_level() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(reason="needs with_outline.pdf fixture")
def test_negative() -> None:  # pragma: no cover
    pass


def test_insert_before_blank_page() -> None:
    """``testInsertBeforeBlankPage``."""
    with PDDocument() as document:
        page_one = PDPage()
        page_two = PDPage()
        page_three = PDPage()

        document.add_page(page_one)
        document.add_page(page_two)
        document.get_pages().insert_before(page_three, page_two)

        pages = document.get_pages()
        assert pages.index_of(page_one) == 0
        assert pages.index_of(page_three) == 1
        assert pages.index_of(page_two) == 2


def test_insert_after_blank_page() -> None:
    """``testInsertAfterBlankPage``."""
    with PDDocument() as document:
        page_one = PDPage()
        page_two = PDPage()
        page_three = PDPage()

        document.add_page(page_one)
        document.add_page(page_two)
        document.get_pages().insert_after(page_three, page_two)

        pages = document.get_pages()
        assert pages.index_of(page_one) == 0
        assert pages.index_of(page_two) == 1
        assert pages.index_of(page_three) == 2


# ``testNodeLoop`` — needs the PDFBOX-6040-nodeloop.pdf fixture. Our
# hand-written ``test_inheritable_attribute_breaks_cycles`` covers the
# same loop-protection invariant synthetically.
@pytest.mark.skip(
    reason=(
        "needs PDFBOX-6040-nodeloop.pdf fixture; "
        "cycle protection covered synthetically"
    )
)
def test_node_loop() -> None:  # pragma: no cover
    pass
