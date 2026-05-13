"""Parity tests for upstream-named accessors on
``org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineNode``
and its ``PDDocumentOutline`` subclass.

Pins the surface that PDFBox callers reach for so future refactors
can't silently break the upstream-shaped public API.
"""
from __future__ import annotations

from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
    PDOutlineItemIterator,
)

# ---------- helpers ----------


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


# ---------- has_children ----------


def test_has_children_false_on_empty_outline() -> None:
    parent = PDDocumentOutline()
    assert parent.has_children() is False


def test_has_children_true_after_add_last() -> None:
    parent = PDDocumentOutline()
    parent.add_last(PDOutlineItem())
    assert parent.has_children() is True


def test_has_children_true_after_add_first() -> None:
    parent = PDDocumentOutline()
    parent.add_first(PDOutlineItem())
    assert parent.has_children() is True


# ---------- iterator() yields children in /First → /Next order ----------


def test_iterator_returns_outline_item_iterator_instance() -> None:
    parent, _a, _b, _c = _build_three_item_chain()
    it = parent.iterator()
    assert isinstance(it, PDOutlineItemIterator)


def test_iterator_yields_children_in_first_to_next_chain_order() -> None:
    parent, a, b, c = _build_three_item_chain()
    yielded = list(parent.iterator())
    assert [n.get_cos_object() for n in yielded] == [
        a.get_cos_object(),
        b.get_cos_object(),
        c.get_cos_object(),
    ]


def test_iterator_on_empty_outline_yields_nothing() -> None:
    parent = PDDocumentOutline()
    assert list(parent.iterator()) == []


def test_nodes_alias_yields_same_chain_as_children() -> None:
    parent, a, b, c = _build_three_item_chain()
    via_children = [n.get_cos_object() for n in parent.children()]
    via_nodes = [n.get_cos_object() for n in parent.nodes()]
    assert via_children == via_nodes == [
        a.get_cos_object(),
        b.get_cos_object(),
        c.get_cos_object(),
    ]


# ---------- get_open_count / set_open_count round-trip ----------


def test_get_open_count_default_zero_on_fresh_node() -> None:
    parent = PDDocumentOutline()
    assert parent.get_open_count() == 0


def test_set_open_count_round_trips_positive_value() -> None:
    parent = PDDocumentOutline()
    parent.set_open_count(7)
    assert parent.get_open_count() == 7


def test_set_open_count_round_trips_negative_value() -> None:
    parent = PDDocumentOutline()
    parent.set_open_count(-4)
    assert parent.get_open_count() == -4


def test_set_open_count_round_trips_through_outline_item() -> None:
    item = PDOutlineItem()
    item.set_open_count(12)
    assert item.get_open_count() == 12
    item.set_open_count(-12)
    assert item.get_open_count() == -12


# ---------- PDDocumentOutline.is_open: default + sign semantics ----------


def test_pd_document_outline_is_open_default_true() -> None:
    parent = PDDocumentOutline()
    assert parent.is_open() is True


def test_pd_document_outline_is_open_true_for_positive_count() -> None:
    parent = PDDocumentOutline()
    parent.set_open_count(3)
    assert parent.is_open() is True


def test_pd_document_outline_is_open_true_for_zero_count() -> None:
    parent = PDDocumentOutline()
    parent.set_open_count(0)
    # /Count == 0 is non-negative ⇒ open per spec.
    assert parent.is_open() is True


def test_pd_document_outline_is_open_false_for_negative_count() -> None:
    parent = PDDocumentOutline()
    parent.set_open_count(-2)
    assert parent.is_open() is False


# ---------- open_node / close_node round-trip on populated outline ----------


def test_pd_document_outline_open_close_are_no_ops() -> None:
    parent = PDDocumentOutline()
    parent.set_open_count(3)
    assert parent.is_node_open() is True

    parent.close_node()
    assert parent.get_open_count() == 3
    assert parent.is_node_open() is True

    parent.open_node()
    assert parent.get_open_count() == 3
    assert parent.is_node_open() is True


def test_pd_document_outline_close_node_does_not_flip_negative_count() -> None:
    parent = PDDocumentOutline()
    parent.set_open_count(-3)
    parent.close_node()
    assert parent.get_open_count() == -3
    parent.close_node()
    assert parent.get_open_count() == -3


def test_pd_document_outline_open_node_preserves_count() -> None:
    parent = PDDocumentOutline()
    parent.set_open_count(5)
    assert parent.is_node_open() is True
    parent.open_node()
    assert parent.get_open_count() == 5
