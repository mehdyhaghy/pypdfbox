"""Fuzz / parity tests for the outline bookmark tree.

Hammers ``PDDocumentOutline`` + ``PDOutlineItem`` + ``PDOutlineNode`` linkage:
``/First`` ``/Last`` (child range), ``/Next`` ``/Prev`` (siblings), ``/Parent``,
``/Count`` (signed open/closed convention), ``/Title``, ``/Dest`` vs ``/A``.

Behavioural targets mirror upstream
``org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineNode``
and ``PDOutlineItem`` from PDFBox 3.0.7.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)

_NEXT = COSName.get_pdf_name("Next")
_PARENT = COSName.PARENT  # type: ignore[attr-defined]
_DEST = COSName.get_pdf_name("Dest")
_A = COSName.A  # type: ignore[attr-defined]


def _item(title: str | None = None) -> PDOutlineItem:
    it = PDOutlineItem()
    if title is not None:
        it.set_title(title)
    return it


# ---------- append_child: First/Last/Parent linkage ----------


def test_append_single_child_first_equals_last():
    root = PDDocumentOutline()
    child = _item("a")
    root.append_child(child)
    first = root.get_first_child()
    last = root.get_last_child()
    assert first is not None
    assert last is not None
    # First and Last point at the same COSDictionary for a single child.
    assert first.get_cos_object() is child.get_cos_object()
    assert last.get_cos_object() is child.get_cos_object()


def test_append_child_sets_parent_pointer():
    root = PDDocumentOutline()
    child = _item("a")
    root.append_child(child)
    parent = child.get_parent()
    assert parent is not None
    assert parent.get_cos_object() is root.get_cos_object()


def test_single_child_has_no_siblings():
    root = PDDocumentOutline()
    child = _item("a")
    root.append_child(child)
    assert child.get_next_sibling() is None
    assert child.get_previous_sibling() is None


def test_append_two_children_first_last():
    root = PDDocumentOutline()
    a, b = _item("a"), _item("b")
    root.append_child(a)
    root.append_child(b)
    assert root.get_first_child().get_cos_object() is a.get_cos_object()
    assert root.get_last_child().get_cos_object() is b.get_cos_object()


def test_append_two_children_sibling_chain():
    root = PDDocumentOutline()
    a, b = _item("a"), _item("b")
    root.append_child(a)
    root.append_child(b)
    assert a.get_next_sibling().get_cos_object() is b.get_cos_object()
    assert b.get_previous_sibling().get_cos_object() is a.get_cos_object()
    assert a.get_previous_sibling() is None
    assert b.get_next_sibling() is None


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 13])
def test_append_n_children_chain_integrity(n):
    root = PDDocumentOutline()
    items = [_item(f"t{i}") for i in range(n)]
    for it in items:
        root.append_child(it)
    # First/Last anchors.
    assert root.get_first_child().get_cos_object() is items[0].get_cos_object()
    assert root.get_last_child().get_cos_object() is items[-1].get_cos_object()
    # Forward chain.
    cursor = root.get_first_child()
    walked = []
    while cursor is not None:
        walked.append(cursor.get_cos_object())
        cursor = cursor.get_next_sibling()
    assert walked == [it.get_cos_object() for it in items]
    # Backward chain.
    cursor = root.get_last_child()
    back = []
    while cursor is not None:
        back.append(cursor.get_cos_object())
        cursor = cursor.get_previous_sibling()
    assert back == [it.get_cos_object() for it in reversed(items)]


# ---------- children() iteration ----------


@pytest.mark.parametrize("n", [0, 1, 2, 4, 7])
def test_children_iteration_order(n):
    root = PDDocumentOutline()
    titles = [f"x{i}" for i in range(n)]
    for t in titles:
        root.append_child(_item(t))
    got = [c.get_title() for c in root.children()]
    assert got == titles


def test_children_reiterable():
    root = PDDocumentOutline()
    for t in ["a", "b", "c"]:
        root.append_child(_item(t))
    first_pass = [c.get_title() for c in root.children()]
    second_pass = [c.get_title() for c in root.children()]
    assert first_pass == second_pass == ["a", "b", "c"]


def test_iterator_has_next_terminates():
    root = PDDocumentOutline()
    for t in ["a", "b"]:
        root.append_child(_item(t))
    it = root.iterator()
    seen = []
    while it.has_next():
        seen.append(it.next().get_title())
    assert seen == ["a", "b"]
    assert it.has_next() is False


def test_dunder_iter_matches_children():
    root = PDDocumentOutline()
    for t in ["p", "q", "r"]:
        root.append_child(_item(t))
    assert [c.get_title() for c in root] == ["p", "q", "r"]


# ---------- cycle guard: malformed /Next loop must terminate ----------


def test_children_iteration_cycle_guard():
    root = PDDocumentOutline()
    a, b = _item("a"), _item("b")
    root.append_child(a)
    root.append_child(b)
    # Forge a cycle: b.Next -> a (malformed).
    b.get_cos_object().set_item(_NEXT, a.get_cos_object())
    titles = []
    for c in root.children():
        titles.append(c.get_title())
        if len(titles) > 10:  # pragma: no cover - safety net if guard fails
            pytest.fail("children() did not terminate on cyclic /Next")
    # Must terminate; each node visited at most once.
    assert titles == ["a", "b"]


def test_self_referential_next_cycle_terminates():
    root = PDDocumentOutline()
    a = _item("a")
    root.append_child(a)
    a.get_cos_object().set_item(_NEXT, a.get_cos_object())
    titles = [c.get_title() for c in root.children()]
    assert titles == ["a"]


def test_iterator_next_raises_stopiteration_on_cycle():
    a, b = _item("a"), _item("b")
    a.set_next_sibling(b)
    b.set_next_sibling(a)
    from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_node import (
        PDOutlineItemIterator,
    )

    it = PDOutlineItemIterator(a)
    collected = list(it)
    assert [c.get_title() for c in collected] == ["a", "b"]


# ---------- /Count sign: open positive, closed negative ----------


def test_fresh_parent_closed_so_children_make_count_negative():
    # A freshly created item has /Count absent (== 0), so isNodeOpen() is
    # false (0 is not > 0). Appending children to it therefore drives
    # /Count *negative* and does not bubble to the grandparent — upstream
    # PDOutlineNode#updateParentOpenCount with a closed parent.
    root = PDDocumentOutline()
    parent = _item("p")
    root.append_child(parent)
    leaf = _item("leaf")
    parent.append_child(leaf)
    assert parent.get_open_count() == -1
    assert not parent.is_node_open()


def test_explicitly_open_parent_accumulates_positive_count():
    root = PDDocumentOutline()
    parent = _item("p")
    root.append_child(parent)
    # Force the parent open before adding children.
    parent.set_open_count(1)
    assert parent.is_node_open()
    parent.append_child(_item("leaf"))
    # Open parent: the child adds directly (+1).
    assert parent.get_open_count() == 2
    assert parent.is_node_open()


def test_close_node_flips_count_sign_negative():
    parent = _item("p")
    # Pre-seed an open parent with two visible descendants.
    parent.set_open_count(2)
    assert parent.is_node_open()
    parent.close_node()
    assert parent.get_open_count() == -2
    assert not parent.is_node_open()
    assert parent.is_collapsed()


def test_open_node_flips_count_sign_positive():
    parent = _item("p")
    parent.set_open_count(-3)
    assert not parent.is_node_open()
    parent.open_node()
    assert parent.get_open_count() == 3
    assert parent.is_node_open()


def test_open_node_noop_when_already_open():
    parent = _item("p")
    parent.set_open_count(2)
    parent.open_node()
    assert parent.get_open_count() == 2


def test_close_node_noop_when_already_closed():
    parent = _item("p")
    parent.set_open_count(-2)
    parent.close_node()
    assert parent.get_open_count() == -2


def test_close_node_zero_count_stays_zero():
    leaf = _item("leaf")
    assert leaf.get_open_count() == 0
    leaf.close_node()  # is_node_open() is False (0 not > 0), no-op
    assert leaf.get_open_count() == 0


# ---------- open-count propagation to ancestors ----------


def test_open_count_propagates_to_open_parent():
    root = PDDocumentOutline()
    a = _item("a")
    root.append_child(a)
    # root is always open; adding one item -> count 1.
    assert root.get_open_count() == 1
    b = _item("b")
    root.append_child(b)
    assert root.get_open_count() == 2


def test_nested_open_count_bubbles_up_through_open_parent():
    root = PDDocumentOutline()
    parent = _item("parent")
    root.append_child(parent)  # root count +1
    assert root.get_open_count() == 1
    parent.set_open_count(1)  # mark parent open (one notional descendant)
    child = _item("child")
    parent.append_child(child)
    # Open parent absorbs +1 directly and bubbles +1 to the always-open root.
    assert parent.get_open_count() == 2
    assert root.get_open_count() == 2


def test_closed_parent_does_not_bubble_open_count():
    # Build via the real mutation path (mirrors the oracle-verified
    # sequence in test_pd_outline_count_propagation_wave1483): a child is
    # appended (parent closed -> -1), the parent is opened (+1 bubbles to
    # root), then closed again (the swing is withdrawn from the root).
    root = PDDocumentOutline()
    parent = _item("parent")
    parent.append_child(_item("c1"))  # parent closed -> /Count -1
    root.append_child(parent)  # root +1 (just the parent)
    assert root.get_open_count() == 1
    parent.open_node()  # parent 1, root 2
    assert parent.get_open_count() == 1
    assert root.get_open_count() == 2
    # Close the parent again: root open-count loses the descendant.
    parent.close_node()
    assert parent.get_open_count() == -1
    assert root.get_open_count() == 1


def test_add_closed_child_with_descendants_only_counts_itself():
    root = PDDocumentOutline()
    # Pre-build an open subtree off-tree, then close it.
    sub = _item("sub")
    sub.set_open_count(2)  # pretend it has two visible descendants, open
    sub.close_node()
    assert sub.get_open_count() == -2
    # Attaching a *closed* child to root contributes only +1 (the child).
    root.append_child(sub)
    assert root.get_open_count() == 1


# ---------- insert_sibling_after ----------


def test_insert_sibling_after_middle():
    root = PDDocumentOutline()
    a, c = _item("a"), _item("c")
    root.append_child(a)
    root.append_child(c)
    b = _item("b")
    a.insert_sibling_after(b)
    assert [x.get_title() for x in root.children()] == ["a", "b", "c"]
    assert b.get_previous_sibling().get_cos_object() is a.get_cos_object()
    assert b.get_next_sibling().get_cos_object() is c.get_cos_object()


def test_insert_sibling_after_tail_updates_last():
    root = PDDocumentOutline()
    a = _item("a")
    root.append_child(a)
    b = _item("b")
    a.insert_sibling_after(b)
    assert root.get_last_child().get_cos_object() is b.get_cos_object()
    assert b.get_next_sibling() is None


def test_insert_sibling_after_updates_open_count():
    root = PDDocumentOutline()
    a = _item("a")
    root.append_child(a)
    assert root.get_open_count() == 1
    a.insert_sibling_after(_item("b"))
    assert root.get_open_count() == 2


def test_insert_sibling_before_head_updates_first():
    root = PDDocumentOutline()
    b = _item("b")
    root.append_child(b)
    a = _item("a")
    b.insert_sibling_before(a)
    assert root.get_first_child().get_cos_object() is a.get_cos_object()
    assert [x.get_title() for x in root.children()] == ["a", "b"]


def test_require_single_node_rejects_attached_sibling():
    root = PDDocumentOutline()
    a, b = _item("a"), _item("b")
    root.append_child(a)
    root.append_child(b)
    # b is attached (has /Prev) — cannot be inserted again.
    with pytest.raises(ValueError):
        a.insert_sibling_after(b)


# ---------- removing children ----------


def test_remove_only_child_clears_first_and_last():
    root = PDDocumentOutline()
    a = _item("a")
    root.append_child(a)
    assert root.remove_child(a) is True
    assert root.get_first_child() is None
    assert root.get_last_child() is None
    assert root.has_children() is False
    assert a.get_cos_object().get_dictionary_object(_PARENT) is None


def test_remove_all_children_one_by_one():
    root = PDDocumentOutline()
    items = [_item(f"t{i}") for i in range(4)]
    for it in items:
        root.append_child(it)
    assert root.get_open_count() == 4
    for it in items:
        assert root.remove_child(it) is True
    assert root.has_children() is False
    assert root.get_open_count() == 0


def test_remove_middle_child_relinks_siblings():
    root = PDDocumentOutline()
    a, b, c = _item("a"), _item("b"), _item("c")
    for it in (a, b, c):
        root.append_child(it)
    assert root.remove_child(b) is True
    assert [x.get_title() for x in root.children()] == ["a", "c"]
    assert a.get_next_sibling().get_cos_object() is c.get_cos_object()
    assert c.get_previous_sibling().get_cos_object() is a.get_cos_object()


def test_remove_head_updates_first_and_prev():
    root = PDDocumentOutline()
    a, b = _item("a"), _item("b")
    root.append_child(a)
    root.append_child(b)
    assert root.remove_child(a) is True
    assert root.get_first_child().get_cos_object() is b.get_cos_object()
    assert b.get_previous_sibling() is None


def test_remove_tail_updates_last_and_next():
    root = PDDocumentOutline()
    a, b = _item("a"), _item("b")
    root.append_child(a)
    root.append_child(b)
    assert root.remove_child(b) is True
    assert root.get_last_child().get_cos_object() is a.get_cos_object()
    assert a.get_next_sibling() is None


def test_remove_absent_child_returns_false():
    root = PDDocumentOutline()
    root.append_child(_item("a"))
    stranger = _item("z")
    assert root.remove_child(stranger) is False


def test_remove_child_cyclic_chain_returns_false():
    root = PDDocumentOutline()
    a, b = _item("a"), _item("b")
    root.append_child(a)
    root.append_child(b)
    b.get_cos_object().set_item(_NEXT, a.get_cos_object())  # cycle
    stranger = _item("z")
    # Must terminate (not loop forever) and report not-found.
    assert root.remove_child(stranger) is False


# ---------- title get/set ----------


def test_title_roundtrip():
    it = _item()
    assert it.get_title() is None
    it.set_title("Chapter 1")
    assert it.get_title() == "Chapter 1"


def test_title_unicode_roundtrip():
    it = _item()
    it.set_title("Café — Über §")
    assert it.get_title() == "Café — Über §"


def test_title_clear_with_none():
    it = _item("x")
    it.set_title(None)
    assert it.get_title() is None


# ---------- /Dest vs /A retrieval ----------


def test_action_retrieval():
    it = _item()
    assert it.has_action() is False
    assert it.get_action() is None
    action_dict = COSDictionary()
    action_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("GoTo"))
    it.get_cos_object().set_item(_A, action_dict)
    assert it.has_action() is True
    assert it.get_action() is not None


def test_destination_retrieval_and_clear():
    it = _item()
    assert it.has_destination() is False
    dest_arr = COSArray()
    dest_arr.add(COSInteger.get(0))
    dest_arr.add(COSName.get_pdf_name("Fit"))
    it.get_cos_object().set_item(_DEST, dest_arr)
    assert it.has_destination() is True
    assert it.get_destination() is not None
    it.clear_destination()
    assert it.has_destination() is False


def test_dest_and_action_independent():
    it = _item()
    action_dict = COSDictionary()
    action_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("GoTo"))
    it.set_action(it.get_action())  # no-op None
    it.get_cos_object().set_item(_A, action_dict)
    dest_arr = COSArray()
    dest_arr.add(COSInteger.get(2))
    dest_arr.add(COSName.get_pdf_name("Fit"))
    it.get_cos_object().set_item(_DEST, dest_arr)
    assert it.has_action() is True
    assert it.has_destination() is True
    it.clear_action()
    assert it.has_action() is False
    assert it.has_destination() is True


# ---------- document outline root: count never goes negative ----------


def test_document_outline_is_node_open_always_true():
    root = PDDocumentOutline()
    root.set_open_count(-5)
    # Upstream hard-codes True for the root.
    assert root.is_node_open() is True


def test_document_outline_open_close_noop():
    root = PDDocumentOutline()
    root.append_child(_item("a"))
    before = root.get_open_count()
    root.open_node()
    root.close_node()
    assert root.get_open_count() == before


def test_document_outline_type_marker():
    d = COSDictionary()
    PDDocumentOutline(d)
    assert d.get_dictionary_object(COSName.TYPE) == COSName.get_pdf_name("Outlines")
