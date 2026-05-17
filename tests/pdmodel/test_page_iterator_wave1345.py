"""Wave 1345: residual coverage for ``PageIterator``.

Targets:
  - the non-COSDictionary kid skip branch (line 51);
  - the implicit-page fallback when ``/Type`` is missing AND there is no
    ``/Kids`` entry (line 62-65);
  - the ``_is_page_tree_node(None)`` shortcut (line 70);
  - the ``__next__`` /Type-repair path: missing /Type is rewritten to
    ``/Page`` (line 95);
  - the ``__next__`` /Type-mismatch raise path (line 97).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull
from pypdfbox.pdmodel import PageIterator


def _page() -> COSDictionary:
    d = COSDictionary()
    d.set_name("Type", "Page")
    return d


def _pages_node(*kids: COSDictionary) -> COSDictionary:
    n = COSDictionary()
    n.set_name("Type", "Pages")
    arr = COSArray()
    for kid in kids:
        arr.add(kid)
    n.set_item("Kids", arr)
    return n


def test_kids_entry_that_is_not_a_dictionary_is_skipped() -> None:
    """A non-dictionary entry in /Kids is silently skipped (line 51)."""
    root = COSDictionary()
    root.set_name("Type", "Pages")
    arr = COSArray()
    arr.add(COSNull.NULL)  # non-dict entry
    arr.add(_page())       # valid page after
    root.set_item("Kids", arr)
    pages = list(PageIterator(root))
    assert len(pages) == 1


def test_leaf_with_no_type_and_no_kids_is_treated_as_page() -> None:
    """A leaf-shaped node without /Type is accepted as a page (line 62-65)."""
    leaf = COSDictionary()  # no /Type, no /Kids
    # The root must be recognised as a tree node so the leaf is enqueued
    # as a kid (otherwise the root itself would walk the leaf branch).
    root = _pages_node(leaf)
    pages = list(PageIterator(root))
    assert len(pages) == 1


def test_is_page_tree_node_returns_false_for_none_node() -> None:
    """The private static helper handles ``None`` (line 70)."""
    assert PageIterator._is_page_tree_node(None) is False


def test_next_repairs_missing_type_to_page() -> None:
    """A queued page without /Type has it set to /Page on dequeue (line 95)."""
    leaf = COSDictionary()  # no /Type
    root = _pages_node(leaf)
    it = PageIterator(root)
    page = it.next()
    # The leaf's /Type must now be COSName('Page').
    type_name = leaf.get_dictionary_object(COSName.get_pdf_name("Type"))
    assert isinstance(type_name, COSName)
    assert type_name == COSName.get_pdf_name("Page")
    assert page is not None


def test_next_raises_when_type_is_wrong_cos_name() -> None:
    """A queued node whose /Type is set to something other than /Page
    raises ``RuntimeError`` on dequeue (line 97).

    To reach this branch we hand-build a /Kids array that already contains
    the offending kid (PageIterator only enqueues leaves whose /Type is
    /Page or missing) — we mutate the kid AFTER iterator construction so
    it is on the queue with a /Type override.
    """
    leaf = COSDictionary()  # construction time: no /Type, becomes a queued leaf
    root = _pages_node(leaf)
    it = PageIterator(root)
    # Stamp /Type to something other than /Page before __next__ runs.
    leaf.set_name("Type", "NotAPage")
    with pytest.raises(RuntimeError, match="Expected 'Page'"):
        it.next()


def test_iter_returns_self() -> None:
    """``__iter__`` yields the iterator itself."""
    root = _pages_node()
    it = PageIterator(root)
    assert iter(it) is it
