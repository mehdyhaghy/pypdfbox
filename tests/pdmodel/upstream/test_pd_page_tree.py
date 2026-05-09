"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDPageTree.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDPageTree


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


def test_node_loop() -> None:
    """``testNodeLoop`` / PDFBOX-6040: resource inheritance must terminate."""
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    root_kids = COSArray()
    root.set_item(COSName.KIDS, root_kids)  # type: ignore[attr-defined]
    root.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]

    loop = COSDictionary()
    loop.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    loop_kids = COSArray()
    loop.set_item(COSName.KIDS, loop_kids)  # type: ignore[attr-defined]
    loop.set_item(COSName.PARENT, loop)  # type: ignore[attr-defined]
    loop.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]
    root_kids.add(loop)

    raw_page = COSDictionary()
    raw_page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    raw_page.set_item(COSName.PARENT, loop)  # type: ignore[attr-defined]
    loop_kids.add(raw_page)

    page = PDPageTree(root).get(0)

    assert page.get_cos_object() is raw_page
    assert page.get_inherited_cos_object(COSName.RESOURCES) is None  # type: ignore[attr-defined]
    assert (
        PDPageTree.get_inheritable_attribute(raw_page, COSName.RESOURCES)  # type: ignore[attr-defined]
        is None
    )
    assert page.get_resources().get_cos_object().is_empty()
