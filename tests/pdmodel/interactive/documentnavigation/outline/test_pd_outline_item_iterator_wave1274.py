from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_node import (
    PDOutlineItemIterator,
)


def _outline_with_two_children() -> PDDocumentOutline:
    outline = PDDocumentOutline()
    first = PDOutlineItem()
    second = PDOutlineItem()
    outline.add_last(first)
    outline.add_last(second)
    return outline


def test_next_returns_same_items_as_dunder_next() -> None:
    """``next()`` is a Java-style alias for ``__next__()``."""
    outline = _outline_with_two_children()
    children = list(outline.children())
    iterator = PDOutlineItemIterator(outline.get_first_child())
    assert iterator.next().get_cos_object() is children[0].get_cos_object()
    assert iterator.next().get_cos_object() is children[1].get_cos_object()


def test_next_raises_stop_iteration_when_exhausted() -> None:
    """When the chain is exhausted ``next`` raises ``StopIteration`` —
    Python's protocol stand-in for upstream's ``NoSuchElementException``."""
    outline = _outline_with_two_children()
    iterator = PDOutlineItemIterator(outline.get_first_child())
    iterator.next()
    iterator.next()
    with pytest.raises(StopIteration):
        iterator.next()


def test_next_on_empty_iterator() -> None:
    """An iterator over a missing first-child raises immediately."""
    iterator = PDOutlineItemIterator(None)
    with pytest.raises(StopIteration):
        iterator.next()
