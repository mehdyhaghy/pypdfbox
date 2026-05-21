"""Port of upstream ``PDOutlineItemIteratorTest`` (PDFBox 3.0.x).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/
documentnavigation/outline/PDOutlineItemIteratorTest.java``.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDOutlineItem,
    PDOutlineItemIterator,
)


def test_single_item() -> None:
    first = PDOutlineItem()
    iterator = PDOutlineItemIterator(first)
    assert iterator.has_next()
    # ``==`` (PDDictionaryWrapper equality on the backing COSDictionary)
    # mirrors upstream ``assertEquals`` since ``PDOutlineItem`` always
    # returns a fresh wrapper around the same dictionary on each lookup.
    assert iterator.next() == first
    assert not iterator.has_next()


def test_multiple_item() -> None:
    first = PDOutlineItem()
    second = PDOutlineItem()
    first.set_next_sibling(second)
    iterator = PDOutlineItemIterator(first)
    assert iterator.has_next()
    assert iterator.next() == first
    assert iterator.has_next()
    assert iterator.next() == second
    assert not iterator.has_next()


def test_remove_unsupported() -> None:
    iterator = PDOutlineItemIterator(PDOutlineItem())
    # Upstream raises ``UnsupportedOperationException``; the Python equivalent
    # is ``NotImplementedError`` (the canonical "method is not supported"
    # marker for the iterator protocol).
    with pytest.raises(NotImplementedError):
        iterator.remove()


def test_no_children() -> None:
    iterator = PDOutlineItemIterator(None)
    assert not iterator.has_next()
