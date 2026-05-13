"""Hand-written tests for ``pypdfbox.debugger.ui.PageEntry``."""

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.debugger.ui import PageEntry


def _make_leaf_page() -> COSDictionary:
    page = COSDictionary()
    page.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page"))
    return page


def test_basics() -> None:
    page = _make_leaf_page()
    entry = PageEntry(page, 3, "iii")
    assert entry.get_dict() is page
    assert entry.get_page_num() == 3
    assert str(entry) == "Page: 3 - iii"


def test_str_without_label() -> None:
    entry = PageEntry(_make_leaf_page(), 1, None)
    assert str(entry) == "Page: 1"


def test_get_path_walks_to_root() -> None:
    # Build a small Pages tree:  root -> kids[0] = inner -> kids[1] = page
    root = COSDictionary()
    inner = COSDictionary()
    page = _make_leaf_page()

    inner_kids = COSArray()
    inner_kids.add(COSDictionary())  # filler at index 0
    inner_kids.add(page)              # page sits at index 1
    inner.set_item(COSName.KIDS, inner_kids)

    root_kids = COSArray()
    root_kids.add(inner)              # inner at index 0
    root.set_item(COSName.KIDS, root_kids)

    # wire parents
    inner.set_item(COSName.PARENT, root)
    page.set_item(COSName.PARENT, inner)

    entry = PageEntry(page, 1, None)
    # The walk pushes ``/Kids/[<idx>]`` from leaf-toward-root.
    assert entry.get_path() == "Root/Pages/Kids/[1]/Kids/[0]"


def test_get_path_with_no_parent() -> None:
    entry = PageEntry(_make_leaf_page(), 1, None)
    assert entry.get_path() == "Root/Pages"


def test_get_path_returns_empty_when_parent_value_not_dict() -> None:
    """``/Parent`` resolves to a non-dictionary → walker bails out with ``""``."""
    page = _make_leaf_page()
    # ``get_cos_dictionary`` returns ``None`` when /Parent is not a dict.
    page.set_item(COSName.PARENT, COSName.get_pdf_name("BogusNonDict"))
    entry = PageEntry(page, 1, None)
    assert entry.get_path() == ""


def test_get_path_returns_empty_when_parent_has_no_kids() -> None:
    """``/Parent`` dict missing ``/Kids`` → walker bails out with ``""``."""
    page = _make_leaf_page()
    parent = COSDictionary()  # no /Kids
    page.set_item(COSName.PARENT, parent)
    entry = PageEntry(page, 1, None)
    assert entry.get_path() == ""


def test_get_path_breaks_when_page_not_in_kids() -> None:
    """``/Kids`` array doesn't include the page → loop breaks; partial path."""
    page = _make_leaf_page()
    parent = COSDictionary()
    kids = COSArray()
    kids.add(COSDictionary())  # an unrelated entry
    parent.set_item(COSName.KIDS, kids)
    page.set_item(COSName.PARENT, parent)
    entry = PageEntry(page, 1, None)
    # Walker breaks without appending → just the root.
    assert entry.get_path() == "Root/Pages"
