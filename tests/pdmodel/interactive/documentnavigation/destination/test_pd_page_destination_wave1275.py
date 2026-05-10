"""Wave 1275 parity test for PDPageDestination.index_of_page_tree."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
    PDPageDestination,
)


def _make_pages_root_with_one_page() -> tuple[COSDictionary, COSDictionary]:
    page = COSDictionary()
    page.set_item(COSName.TYPE, COSName.get_pdf_name("Page"))
    pages = COSDictionary()
    pages.set_item(COSName.TYPE, COSName.PAGES)
    kids = COSArray()
    kids.add(page)
    pages.set_item(COSName.KIDS, kids)
    pages.set_int(COSName.get_pdf_name("Count"), 1)
    page.set_item(COSName.PARENT, pages)
    return pages, page


def test_index_of_page_tree_finds_page_at_root() -> None:
    _, page = _make_pages_root_with_one_page()
    assert PDPageDestination.index_of_page_tree(page) == 0


def test_index_of_page_tree_returns_minus_one_for_orphan() -> None:
    orphan = COSDictionary()
    assert PDPageDestination.index_of_page_tree(orphan) == -1


def test_retrieve_page_number_uses_index_of_page_tree() -> None:
    _, page = _make_pages_root_with_one_page()
    arr = COSArray()
    arr.add(page)
    arr.add(COSName.get_pdf_name("Fit"))
    dest = PDPageDestination(arr)
    assert dest.retrieve_page_number() == 0
