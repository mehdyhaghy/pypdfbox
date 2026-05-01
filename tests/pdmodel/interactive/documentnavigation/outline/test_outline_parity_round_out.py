"""Hand-written parity tests pinning the round-out additions to the
``outline`` cluster:

- ``PDOutlineNode.__eq__`` / ``__hash__`` — port of upstream
  ``PDDictionaryWrapper#equals`` / ``#hashCode``: two outline wrappers
  compare equal when (and only when) they share the same wrapped
  ``COSDictionary``. Lets ``assertEquals`` shaped tests work across
  fresh wrappers returned by ``get_next_sibling`` / ``get_first_child``.
- ``PDDocumentOutline.__init__`` always overwrites ``/Type /Outlines``
  on the wrapped dictionary, mirroring upstream's constructor.
- ``PDOutlineItem.set_previous_sibling`` — public alias paired with
  the existing ``set_next_sibling`` for hand-built test fixtures.
- ``PDOutlineItemIterator.has_next`` is cycle-aware: returns ``False``
  once the cursor revisits a previously yielded node, matching upstream
  ``PDOutlineItemIterator#hasNext``.
"""
from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
    PDOutlineItemIterator,
)


# ---------- PDOutlineNode.__eq__ / __hash__ ----------


def test_eq_two_wrappers_around_same_dict_compare_equal() -> None:
    raw = COSDictionary()
    a = PDOutlineItem(raw)
    b = PDOutlineItem(raw)
    assert a == b


def test_eq_two_wrappers_around_distinct_dicts_compare_unequal() -> None:
    a = PDOutlineItem()
    b = PDOutlineItem()
    assert a != b


def test_eq_get_next_sibling_compares_equal_to_original_wrapper() -> None:
    parent = PDDocumentOutline()
    first = PDOutlineItem()
    second = PDOutlineItem()
    parent.add_last(first)
    parent.add_last(second)

    # Each ``get_next_sibling`` call returns a fresh ``PDOutlineItem``
    # wrapping the same dict — without ``__eq__`` parity these would be
    # object-identity-distinct and ``==`` would silently fail.
    assert first.get_next_sibling() == second
    assert second.get_previous_sibling() == first


def test_eq_unrelated_object_returns_not_equal() -> None:
    a = PDOutlineItem()
    assert (a == "not an outline node") is False
    assert (a == 42) is False
    assert (a == None) is False  # noqa: E711 — explicit None check is intentional


def test_hash_round_trip_in_a_set() -> None:
    raw = COSDictionary()
    a = PDOutlineItem(raw)
    b = PDOutlineItem(raw)
    c = PDOutlineItem()  # distinct dict
    bag = {a, b, c}
    # ``a`` and ``b`` collapse (same dict, equal hash + eq); ``c`` is separate.
    assert len(bag) == 2


def test_hash_consistent_with_equality() -> None:
    raw = COSDictionary()
    a = PDOutlineItem(raw)
    b = PDOutlineItem(raw)
    assert a == b
    assert hash(a) == hash(b)


def test_eq_pd_document_outline_vs_pd_outline_item_when_dict_shared() -> None:
    # Cross-class equality across the same dictionary — both are
    # ``PDOutlineNode`` subclasses, so the parity rule applies.
    raw = COSDictionary()
    item = PDOutlineItem(raw)
    root = PDDocumentOutline(raw)
    assert item == root


# ---------- PDDocumentOutline constructor overwrites /Type ----------


def test_pd_document_outline_constructor_overwrites_wrong_type() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("Pages"))  # type: ignore[attr-defined]

    PDDocumentOutline(raw)

    written = raw.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
    assert written == COSName.get_pdf_name("Outlines")


def test_pd_document_outline_constructor_sets_type_when_absent() -> None:
    raw = COSDictionary()
    PDDocumentOutline(raw)
    written = raw.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
    assert written == COSName.get_pdf_name("Outlines")


def test_pd_document_outline_default_constructor_writes_type() -> None:
    outline = PDDocumentOutline()
    written = outline.get_cos_object().get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
    assert written == COSName.get_pdf_name("Outlines")


# ---------- PDOutlineItem.set_previous_sibling ----------


def test_set_previous_sibling_writes_prev_entry() -> None:
    a = PDOutlineItem()
    b = PDOutlineItem()
    a.set_previous_sibling(b)
    assert a.get_previous_sibling() == b


def test_set_previous_sibling_round_trip_through_chain() -> None:
    # Hand-build a two-node chain via the public sibling setters,
    # bypassing add_last / insert_sibling_*. Mirrors how upstream's
    # PDOutlineItemIteratorTest assembles a fixture by hand.
    first = PDOutlineItem()
    second = PDOutlineItem()
    first.set_next_sibling(second)
    second.set_previous_sibling(first)

    assert first.get_next_sibling() == second
    assert second.get_previous_sibling() == first


# ---------- PDOutlineItemIterator.has_next is cycle-aware ----------


def test_iterator_has_next_false_when_cursor_revisits_seen_node() -> None:
    # Hand-build a self-cycle: a single item whose /Next points to itself.
    a = PDOutlineItem()
    a.set_title("A")
    a.set_next_sibling(a)  # cycle

    it = PDOutlineItemIterator(a)
    assert it.has_next() is True
    yielded = next(it)
    assert yielded == a
    # After yielding ``a`` once, the cursor advances to ``a`` again
    # (cycle). has_next must report False rather than ``True`` followed
    # by a StopIteration on next() — that's what upstream guarantees.
    assert it.has_next() is False


def test_iterator_has_next_false_after_full_walk() -> None:
    parent = PDDocumentOutline()
    a = PDOutlineItem()
    b = PDOutlineItem()
    parent.add_last(a)
    parent.add_last(b)

    it = PDOutlineItemIterator(parent.get_first_child())
    assert it.has_next() is True
    next(it)
    assert it.has_next() is True
    next(it)
    assert it.has_next() is False


def test_iterator_has_next_false_for_empty_start() -> None:
    it = PDOutlineItemIterator(None)
    assert it.has_next() is False
