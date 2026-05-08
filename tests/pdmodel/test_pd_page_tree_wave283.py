from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull, COSObject
from pypdfbox.pdmodel import PDPage, PDPageTree

_COUNT = COSName.get_pdf_name("Count")
_KIDS = COSName.get_pdf_name("Kids")
_LABEL = COSName.get_pdf_name("Label")
_PARENT = COSName.get_pdf_name("Parent")
_PAGES = COSName.get_pdf_name("Pages")
_TYPE = COSName.get_pdf_name("Type")


def _make_page(label: str | None = None) -> PDPage:
    page = PDPage()
    if label is not None:
        page.get_cos_object().set_string(_LABEL, label)
    return page


def _page_label(page: PDPage) -> str | None:
    return page.get_cos_object().get_string(_LABEL)


def test_iteration_repairs_null_kid_entries_in_place() -> None:
    page = _make_page("real")
    root = COSDictionary()
    kids = COSArray([COSNull.NULL, page.get_cos_object()])
    root.set_item(_TYPE, _PAGES)
    root.set_item(_KIDS, kids)
    root.set_int(_COUNT, 2)

    pages = list(PDPageTree(root))

    assert len(pages) == 2
    repaired = kids.get(0)
    assert isinstance(repaired, COSDictionary)
    assert repaired.get_name(_TYPE) == "Page"
    assert pages[0].get_cos_object() is repaired
    assert _page_label(pages[1]) == "real"


def test_iteration_repairs_indirect_null_kid_entries_in_place() -> None:
    root = COSDictionary()
    kids = COSArray([COSObject(7, resolved=COSNull.NULL)])
    root.set_item(_TYPE, _PAGES)
    root.set_item(_KIDS, kids)
    root.set_int(_COUNT, 1)

    pages = list(PDPageTree(root))

    assert len(pages) == 1
    repaired = kids.get(0)
    assert isinstance(repaired, COSDictionary)
    assert pages[0].get_cos_object() is repaired


def test_get_repairs_malformed_non_name_type_to_page() -> None:
    tree = PDPageTree()
    page = _make_page("malformed-type")
    page.get_cos_object().set_item(_TYPE, COSInteger.get(17))
    tree.add(page)

    fetched = tree[0]

    assert fetched.get_cos_object() is page.get_cos_object()
    assert fetched.get_cos_object().get_name(_TYPE) == "Page"


def test_has_pages_tracks_empty_and_populated_tree() -> None:
    tree = PDPageTree()

    assert tree.has_pages() is False
    tree.add(_make_page())
    assert tree.has_pages() is True


def test_clear_removes_pages_and_resets_count() -> None:
    tree = PDPageTree()
    first = _make_page("first")
    second = _make_page("second")
    tree.add(first)
    tree.add(second)

    tree.clear()

    assert tree.has_pages() is False
    assert len(tree) == 0
    assert tree.get_count() == 0
    kids = tree.get_cos_object().get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    assert kids.size() == 0
    assert first not in tree
    assert second not in tree


def test_clear_repairs_missing_or_malformed_kids_array() -> None:
    root = COSDictionary()
    root.set_item(_TYPE, _PAGES)
    root.set_item(_KIDS, COSName.get_pdf_name("Bogus"))
    root.set_item(_PARENT, COSName.get_pdf_name("BogusParent"))
    root.set_int(_COUNT, 5)

    tree = PDPageTree(root)
    tree.clear()

    kids = root.get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    assert kids.size() == 0
    assert tree.get_count() == 0
    assert root.get_dictionary_object(_PARENT) == COSName.get_pdf_name("BogusParent")
