"""Parity tests for upstream-named accessors on
``org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem``.

The class shares many APIs with its parent ``PDOutlineNode`` — these
tests pin the surface as observed *through a* ``PDOutlineItem`` so future
refactors that move methods between the two classes can't silently break
the upstream-shaped public API.
"""
from __future__ import annotations

from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)

# ---------- linked-list navigation ----------


def _build_three_item_chain() -> tuple[
    PDDocumentOutline, PDOutlineItem, PDOutlineItem, PDOutlineItem,
]:
    parent = PDDocumentOutline()
    a = PDOutlineItem()
    a.set_title("A")
    b = PDOutlineItem()
    b.set_title("B")
    c = PDOutlineItem()
    c.set_title("C")
    parent.add_last(a)
    parent.add_last(b)
    parent.add_last(c)
    return parent, a, b, c


def test_get_first_child_returns_typed_first_in_chain() -> None:
    parent, a, _b, _c = _build_three_item_chain()
    first = parent.get_first_child()
    assert isinstance(first, PDOutlineItem)
    assert first.get_cos_object() is a.get_cos_object()


def test_get_last_child_returns_typed_last_in_chain() -> None:
    parent, _a, _b, c = _build_three_item_chain()
    last = parent.get_last_child()
    assert isinstance(last, PDOutlineItem)
    assert last.get_cos_object() is c.get_cos_object()


def test_get_next_sibling_walks_chain_left_to_right() -> None:
    _parent, a, b, c = _build_three_item_chain()
    nxt = a.get_next_sibling()
    assert isinstance(nxt, PDOutlineItem)
    assert nxt.get_cos_object() is b.get_cos_object()
    nxt2 = b.get_next_sibling()
    assert isinstance(nxt2, PDOutlineItem)
    assert nxt2.get_cos_object() is c.get_cos_object()
    assert c.get_next_sibling() is None


def test_get_previous_sibling_walks_chain_right_to_left() -> None:
    _parent, a, b, c = _build_three_item_chain()
    prev = c.get_previous_sibling()
    assert isinstance(prev, PDOutlineItem)
    assert prev.get_cos_object() is b.get_cos_object()
    prev2 = b.get_previous_sibling()
    assert isinstance(prev2, PDOutlineItem)
    assert prev2.get_cos_object() is a.get_cos_object()
    assert a.get_previous_sibling() is None


def test_get_parent_returns_owning_outline_node() -> None:
    parent, a, b, c = _build_three_item_chain()
    for child in (a, b, c):
        resolved = child.get_parent()
        assert resolved is not None
        assert resolved.get_cos_object() is parent.get_cos_object()


# ---------- /Count sign semantics ----------


def test_is_node_open_true_for_positive_count() -> None:
    item = PDOutlineItem()
    item.set_count(3)
    assert item.is_node_open() is True


def test_is_node_open_false_for_negative_count() -> None:
    item = PDOutlineItem()
    item.set_count(-3)
    assert item.is_node_open() is False


def test_is_node_open_false_for_zero_count() -> None:
    item = PDOutlineItem()
    assert item.get_count() == 0
    assert item.is_node_open() is False


# ---------- open_node / close_node toggle the /Count sign ----------


def test_close_node_flips_positive_count_to_negative() -> None:
    item = PDOutlineItem()
    item.set_count(5)
    assert item.is_node_open() is True
    item.close_node()
    assert item.get_count() == -5
    assert item.is_node_open() is False


def test_open_node_flips_negative_count_to_positive() -> None:
    item = PDOutlineItem()
    item.set_count(-7)
    assert item.is_node_open() is False
    item.open_node()
    assert item.get_count() == 7
    assert item.is_node_open() is True


def test_open_close_cycle_round_trips_count() -> None:
    item = PDOutlineItem()
    item.set_count(4)
    item.close_node()
    assert item.get_count() == -4
    item.open_node()
    assert item.get_count() == 4
