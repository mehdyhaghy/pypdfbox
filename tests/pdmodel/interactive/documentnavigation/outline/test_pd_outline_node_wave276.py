"""Wave 276 coverage for ``PDOutlineNode`` linked-list edges."""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
    PDOutlineItemIterator,
)

_FIRST = COSName.get_pdf_name("First")
_NEXT = COSName.get_pdf_name("Next")
_PARENT = COSName.PARENT  # type: ignore[attr-defined]
_PREV = COSName.PREV  # type: ignore[attr-defined]


def _item(title: str) -> PDOutlineItem:
    item = PDOutlineItem()
    item.set_title(title)
    return item


def _titles(parent: PDDocumentOutline) -> list[str | None]:
    return [child.get_title() for child in parent.children()]


def test_append_child_updates_parent_links_and_open_count() -> None:
    parent = PDDocumentOutline()
    parent.append_child(_item("A"))

    open_child = _item("B")
    open_child.set_open_count(2)
    parent.append_child(open_child)

    assert _titles(parent) == ["A", "B"]
    assert parent.get_open_count() == 4
    assert parent.get_first_child().get_parent() == parent
    assert parent.get_last_child() == open_child


def test_insert_sibling_before_and_after_splice_edges() -> None:
    parent = PDDocumentOutline()
    middle = _item("B")
    parent.add_last(middle)

    first = _item("A")
    middle.insert_sibling_before(first)
    last = _item("C")
    middle.insert_sibling_after(last)

    assert _titles(parent) == ["A", "B", "C"]
    assert parent.get_first_child() == first
    assert parent.get_last_child() == last
    assert first.get_next_sibling() == middle
    assert last.get_previous_sibling() == middle
    assert parent.get_open_count() == 3


def test_insert_rejects_item_that_already_has_sibling_links() -> None:
    parent = PDDocumentOutline()
    a = _item("A")
    b = _item("B")
    parent.add_last(a)
    parent.add_last(b)

    c = _item("C")
    with pytest.raises(ValueError, match="single node"):
        c.insert_sibling_before(a)
    with pytest.raises(ValueError, match="single node"):
        c.insert_sibling_after(b)


def test_remove_child_unlinks_middle_child_and_decrements_count() -> None:
    parent = PDDocumentOutline()
    a = _item("A")
    b = _item("B")
    c = _item("C")
    parent.add_last(a)
    parent.add_last(b)
    parent.add_last(c)

    assert parent.remove_child(b) is True

    assert _titles(parent) == ["A", "C"]
    assert parent.get_open_count() == 2
    assert a.get_next_sibling() == c
    assert c.get_previous_sibling() == a
    assert b.get_parent() is None
    assert b.get_previous_sibling() is None
    assert b.get_next_sibling() is None


def test_remove_child_unlinks_only_child_and_clears_parent_edges() -> None:
    parent = PDDocumentOutline()
    child = _item("only")
    parent.add_last(child)

    assert parent.remove_child(child) is True

    assert parent.has_children() is False
    assert parent.get_first_child() is None
    assert parent.get_last_child() is None
    assert parent.get_open_count() == 0
    assert child.get_parent() is None


def test_remove_child_absent_item_is_noop() -> None:
    parent = PDDocumentOutline()
    child = _item("child")
    parent.add_last(child)

    assert parent.remove_child(_item("missing")) is False

    assert _titles(parent) == ["child"]
    assert parent.get_open_count() == 1


def test_remove_open_child_decrements_visible_descendant_count() -> None:
    parent = PDDocumentOutline()
    child = _item("open")
    child.set_open_count(2)
    parent.add_last(child)
    assert parent.get_open_count() == 3

    assert parent.remove_child(child) is True

    assert parent.get_open_count() == 0


def test_iterator_remove_is_unsupported() -> None:
    iterator = PDOutlineItemIterator(_item("A"))

    with pytest.raises(NotImplementedError, match="remove is not supported"):
        iterator.remove()


def test_open_close_child_updates_open_parent_count() -> None:
    parent = PDDocumentOutline()
    child = _item("child")
    grandchild = _item("grandchild")
    child.add_last(grandchild)
    parent.add_last(child)
    assert parent.get_open_count() == 1

    child.open_node()
    assert child.get_open_count() == 1
    assert parent.get_open_count() == 2

    child.close_node()
    assert child.get_open_count() == -1
    assert parent.get_open_count() == 1


def test_eq_directly_returns_not_implemented_for_unrelated_type() -> None:
    assert PDOutlineItem().__eq__(object()) is NotImplemented


def test_malformed_first_child_entry_is_treated_as_empty() -> None:
    parent = PDDocumentOutline()
    parent.get_cos_object().set_item(_FIRST, COSString("not a child dict"))

    assert parent.has_children() is False
    assert parent.get_first_child() is None
    assert list(parent.iterator()) == []


def test_remove_child_stops_on_malformed_next_cycle() -> None:
    parent = PDDocumentOutline()
    child = _item("loop")
    parent.add_last(child)
    child.get_cos_object().set_item(_NEXT, child.get_cos_object())

    assert parent.remove_child(_item("missing")) is False
    assert parent.get_first_child() == child
    assert parent.get_open_count() == 1


def test_remove_child_clears_raw_back_link_entries() -> None:
    parent = PDDocumentOutline()
    child = _item("child")
    parent.add_last(child)

    assert parent.remove_child(child) is True

    raw = child.get_cos_object()
    assert raw.get_dictionary_object(_PARENT) is None
    assert raw.get_dictionary_object(_PREV) is None
    assert raw.get_dictionary_object(_NEXT) is None
