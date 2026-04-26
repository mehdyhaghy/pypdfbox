from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.pdmodel import PDPage, PDPageTree


def _make_page(label: str | None = None) -> PDPage:
    page = PDPage()
    if label is not None:
        page.get_cos_object().set_string(COSName.get_pdf_name("Label"), label)
    return page


def _label(page: PDPage) -> str | None:
    return page.get_cos_object().get_string(COSName.get_pdf_name("Label"))


def test_default_construction_empty_tree() -> None:
    tree = PDPageTree()
    assert len(tree) == 0
    assert list(tree) == []


def test_add_appends_to_kids() -> None:
    tree = PDPageTree()
    p1 = _make_page("first")
    p2 = _make_page("second")
    tree.add(p1)
    tree.add(p2)
    assert len(tree) == 2
    labels = [_label(p) for p in tree]
    assert labels == ["first", "second"]


def test_count_property_updated_on_add() -> None:
    tree = PDPageTree()
    tree.add(_make_page())
    tree.add(_make_page())
    count = tree.get_cos_object().get_dictionary_object(COSName.COUNT)  # type: ignore[attr-defined]
    assert isinstance(count, COSInteger)
    assert count.value == 2


def test_index_access_zero_based() -> None:
    tree = PDPageTree()
    pages = [_make_page(f"p{i}") for i in range(3)]
    for p in pages:
        tree.add(p)
    assert _label(tree[0]) == "p0"
    assert _label(tree[2]) == "p2"


def test_negative_index() -> None:
    tree = PDPageTree()
    for i in range(4):
        tree.add(_make_page(f"p{i}"))
    assert _label(tree[-1]) == "p3"
    assert _label(tree[-4]) == "p0"


def test_index_out_of_range_raises() -> None:
    tree = PDPageTree()
    tree.add(_make_page())
    with pytest.raises(IndexError):
        _ = tree[5]
    with pytest.raises(IndexError):
        _ = tree[-2]


def test_index_of_direct_pages() -> None:
    tree = PDPageTree()
    pages = [_make_page(f"p{i}") for i in range(3)]
    for page in pages:
        tree.add(page)

    assert tree.index_of(pages[0]) == 0
    assert tree.index_of(pages[2]) == 2
    assert tree.index_of_page(pages[1]) == 1


def test_index_of_indirect_page_object() -> None:
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    kids = COSArray()
    root.set_item(COSName.KIDS, kids)  # type: ignore[attr-defined]

    first = _make_page("first")
    second = _make_page("second")
    first.get_cos_object().set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    second.get_cos_object().set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    kids.add(COSObject(10, resolved=first.get_cos_object()))
    kids.add(COSObject(11, resolved=second.get_cos_object()))
    root.set_int(COSName.COUNT, 2)  # type: ignore[attr-defined]

    tree = PDPageTree(root)
    assert tree.index_of(first) == 0
    assert tree.index_of(PDPage(second.get_cos_object())) == 1


def test_index_of_missing_page_returns_minus_one() -> None:
    tree = PDPageTree()
    tree.add(_make_page("present"))

    assert tree.index_of(_make_page("missing")) == -1


def test_remove_decrements_count() -> None:
    tree = PDPageTree()
    p1 = _make_page("a")
    p2 = _make_page("b")
    tree.add(p1)
    tree.add(p2)
    assert tree.remove(p1) is True
    assert len(tree) == 1
    assert _label(tree[0]) == "b"


def test_remove_unknown_returns_false() -> None:
    tree = PDPageTree()
    tree.add(_make_page("a"))
    other = _make_page("b")
    # ``other`` was never added, so its parent doesn't reference it.
    assert tree.remove(other) is False


def test_insert_before() -> None:
    tree = PDPageTree()
    a = _make_page("a")
    c = _make_page("c")
    tree.add(a)
    tree.add(c)
    b = _make_page("b")
    tree.insert_before(b, c)
    assert [_label(p) for p in tree] == ["a", "b", "c"]


def test_insert_after() -> None:
    tree = PDPageTree()
    a = _make_page("a")
    c = _make_page("c")
    tree.add(a)
    tree.add(c)
    b = _make_page("b")
    tree.insert_after(b, a)
    assert [_label(p) for p in tree] == ["a", "b", "c"]


def test_iterates_nested_page_tree() -> None:
    """Nested intermediate /Pages node must be flattened in document order."""
    inner = COSDictionary()
    inner.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    inner_kids = COSArray()
    inner.set_item(COSName.KIDS, inner_kids)  # type: ignore[attr-defined]
    leaf1 = _make_page("a")
    leaf2 = _make_page("b")
    leaf1.get_cos_object().set_item(COSName.PARENT, inner)  # type: ignore[attr-defined]
    leaf2.get_cos_object().set_item(COSName.PARENT, inner)  # type: ignore[attr-defined]
    inner_kids.add(leaf1.get_cos_object())
    inner_kids.add(leaf2.get_cos_object())
    inner.set_int(COSName.COUNT, 2)  # type: ignore[attr-defined]

    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    root_kids = COSArray()
    root.set_item(COSName.KIDS, root_kids)  # type: ignore[attr-defined]
    root_kids.add(inner)
    inner.set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    leaf3 = _make_page("c")
    leaf3.get_cos_object().set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    root_kids.add(leaf3.get_cos_object())
    root.set_int(COSName.COUNT, 3)  # type: ignore[attr-defined]

    tree = PDPageTree(root)
    assert [_label(p) for p in tree] == ["a", "b", "c"]
    assert len(tree) == 3


def test_get_inheritable_attribute() -> None:
    grandparent = COSDictionary()
    grandparent.set_int(COSName.get_pdf_name("Rotate"), 90)
    parent = COSDictionary()
    parent.set_item(COSName.PARENT, grandparent)  # type: ignore[attr-defined]
    leaf = COSDictionary()
    leaf.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]

    value = PDPageTree.get_inheritable_attribute(leaf, COSName.get_pdf_name("Rotate"))
    assert isinstance(value, COSInteger)
    assert value.value == 90


def test_inheritable_attribute_missing_returns_none() -> None:
    leaf = COSDictionary()
    assert PDPageTree.get_inheritable_attribute(leaf, COSName.get_pdf_name("Foo")) is None


def test_inheritable_attribute_breaks_cycles() -> None:
    """A pathological /Parent cycle must not loop forever."""
    a = COSDictionary()
    b = COSDictionary()
    a.set_item(COSName.PARENT, b)  # type: ignore[attr-defined]
    b.set_item(COSName.PARENT, a)  # type: ignore[attr-defined]
    assert PDPageTree.get_inheritable_attribute(a, COSName.get_pdf_name("X")) is None


def test_count_recomputed_when_stored_count_wrong() -> None:
    """If /Count disagrees with the actual walk, the walk wins."""
    tree = PDPageTree()
    tree.add(_make_page())
    tree.add(_make_page())
    # Stomp on /Count to lie about the size.
    tree.get_cos_object().set_int(COSName.COUNT, 99)  # type: ignore[attr-defined]
    assert len(tree) == 2  # walk wins
