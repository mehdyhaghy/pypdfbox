"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDPageTree.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDPageTree

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "pdmodel"
_WITH_OUTLINE = _FIXTURES / "with_outline.pdf"
_MULTI_LEVEL = _FIXTURES / "page_tree_multiple_levels.pdf"


def test_index_of_page_from_outline_destination() -> None:
    """``indexOfPageFromOutlineDestination``."""
    with PDDocument.load(_WITH_OUTLINE) as doc:
        outline = doc.get_document_catalog().get_document_outline()
        assert outline is not None
        for current in outline.children():
            title = current.get_title()
            if title is not None and "Second" in title:
                dest_page = current.find_destination_page(doc)
                assert doc.get_pages().index_of(dest_page) == 2


def test_positive_single_level() -> None:
    """``positiveSingleLevel`` — every page's tree index matches its slot."""
    with PDDocument.load(_WITH_OUTLINE) as doc:
        for i in range(doc.get_number_of_pages()):
            assert doc.get_pages().index_of(doc.get_page(i)) == i


def test_positive_multiple_level() -> None:
    """``positiveMultipleLevel`` — same invariant against a multi-level tree."""
    with PDDocument.load(_MULTI_LEVEL) as doc:
        for i in range(doc.get_number_of_pages()):
            assert doc.get_pages().index_of(doc.get_page(i)) == i


def test_negative() -> None:
    """``negative`` — a page that isn't in the tree returns -1."""
    with PDDocument.load(_WITH_OUTLINE) as doc:
        assert doc.get_pages().index_of(PDPage()) == -1


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
