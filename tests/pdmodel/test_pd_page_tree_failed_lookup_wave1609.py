"""PDFBOX-6286: a failed ``PDPageTree.get`` must not poison later lookups."""

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName


def test_out_of_range_then_valid_lookup() -> None:
    with PDDocument() as document:
        page = PDPage()
        document.add_page(page)
        pages = document.get_pages()
        with pytest.raises(IndexError):
            pages.get(5)
        assert pages.get(0).get_cos_object() is page.get_cos_object()
        assert not pages._page_set


def test_negative_index_does_not_poison() -> None:
    with PDDocument() as document:
        document.add_page(PDPage())
        pages = document.get_pages()
        with pytest.raises(IndexError):
            pages.get(-5)
        assert pages.get(0) is not None


def test_not_found_then_valid_lookup() -> None:
    # /Count claims two pages but /Kids only holds one: page 2 is "not found".
    with PDDocument() as document:
        document.add_page(PDPage())
        pages = document.get_pages()
        root = pages.get_cos_object()
        root.set_int(COSName.COUNT, 2)  # type: ignore[attr-defined]
        with pytest.raises(RuntimeError, match="not found"):
            pages.get(1)
        assert not pages._page_set
        assert pages.get(0) is not None


def test_nested_out_of_range_then_valid_lookup() -> None:
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    kids = COSArray()
    root.set_item(COSName.KIDS, kids)  # type: ignore[attr-defined]
    root.set_int(COSName.COUNT, 2)  # type: ignore[attr-defined]
    inner = COSDictionary()
    inner.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    inner_kids = COSArray()
    inner.set_item(COSName.KIDS, inner_kids)  # type: ignore[attr-defined]
    inner.set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    inner.set_int(COSName.COUNT, 2)  # type: ignore[attr-defined]
    kids.add(inner)
    for _ in range(2):
        leaf = COSDictionary()
        leaf.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
        leaf.set_item(COSName.PARENT, inner)  # type: ignore[attr-defined]
        inner_kids.add(leaf)
    from pypdfbox.pdmodel import PDPageTree

    pages = PDPageTree(root)
    with pytest.raises(IndexError):
        pages.get(7)
    assert pages.get(1).get_cos_object() is inner_kids.get_object(1)
    assert pages.get(0).get_cos_object() is inner_kids.get_object(0)
