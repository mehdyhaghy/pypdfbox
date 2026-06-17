"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/outline/PDOutlineNodeTest.java``
(upstream PDFBox 3.0.x).

JUnit 5 → pytest mapping per the project's "Test Porting Conventions":

* ``@BeforeEach setUp`` → ``setup_method`` instance hook on a class.
* ``assertEquals(expected, actual)`` → ``assert actual == expected``.
* ``assertNull(x)`` → ``assert x is None``.
* ``assertNotEquals(a, b)`` → ``assert a != b``.
* ``assertThrows(IllegalArgumentException, ...)`` →
  ``pytest.raises(ValueError)`` (Python's stand-in for upstream's
  ``IllegalArgumentException`` — flagged in ``CHANGES.md``).

The empty upstream ``openNodeAndAppend`` test (``// TODO``) is skipped
with a one-line comment, in line with the project's skip guidance.
"""
from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)


class TestPDOutlineNode:
    """Mirrors upstream ``PDOutlineNodeTest`` class layout (one shared
    ``root`` per test built in :meth:`setup_method`)."""

    def setup_method(self) -> None:
        self.root = PDOutlineItem()

    # ---- get_parent ----

    def test_get_parent(self) -> None:
        child = PDOutlineItem()
        self.root.add_last(child)
        outline = PDDocumentOutline()
        outline.add_last(self.root)
        assert outline.get_parent() is None
        assert self.root.get_parent() == outline
        assert child.get_parent() == self.root

    # ---- empty-tree accessors ----

    def test_null_last_child(self) -> None:
        assert self.root.get_last_child() is None

    def test_null_first_child(self) -> None:
        assert self.root.get_first_child() is None

    # ---- open / close idempotency ----

    def test_open_already_opened_root_node(self) -> None:
        child = PDOutlineItem()
        assert self.root.get_open_count() == 0
        self.root.add_last(child)
        self.root.open_node()
        assert self.root.is_node_open() is True
        assert self.root.get_open_count() == 1
        self.root.open_node()
        assert self.root.is_node_open() is True
        assert self.root.get_open_count() == 1

    def test_close_already_closed_root_node(self) -> None:
        child = PDOutlineItem()
        assert self.root.get_open_count() == 0
        self.root.add_last(child)
        self.root.open_node()
        self.root.close_node()
        assert self.root.is_node_open() is False
        assert self.root.get_open_count() == -1
        self.root.close_node()
        assert self.root.is_node_open() is False
        assert self.root.get_open_count() == -1

    def test_open_leaf(self) -> None:
        child = PDOutlineItem()
        self.root.add_last(child)
        child.open_node()
        assert child.is_node_open() is False

    def test_node_closed_by_default(self) -> None:
        child = PDOutlineItem()
        self.root.add_last(child)
        assert self.root.is_node_open() is False
        assert self.root.get_open_count() == -1

    # ---- open/close propagating into a parent's count ----

    def test_close_node_with_opened_parent(self) -> None:
        child = PDOutlineItem()
        child.add_last(PDOutlineItem())
        child.add_last(PDOutlineItem())
        child.open_node()
        self.root.add_last(child)
        self.root.open_node()
        assert self.root.get_open_count() == 3
        assert child.get_open_count() == 2
        child.close_node()
        assert self.root.get_open_count() == 1
        assert child.get_open_count() == -2

    def test_close_node_with_closed_parent(self) -> None:
        child = PDOutlineItem()
        child.add_last(PDOutlineItem())
        child.add_last(PDOutlineItem())
        child.open_node()
        self.root.add_last(child)
        assert self.root.get_open_count() == -3
        assert child.get_open_count() == 2
        child.close_node()
        assert self.root.get_open_count() == -1
        assert child.get_open_count() == -2

    def test_open_node_with_opened_parent(self) -> None:
        child = PDOutlineItem()
        child.add_last(PDOutlineItem())
        child.add_last(PDOutlineItem())
        self.root.add_last(child)
        self.root.open_node()
        assert self.root.get_open_count() == 1
        assert child.get_open_count() == -2
        child.open_node()
        assert self.root.get_open_count() == 3
        assert child.get_open_count() == 2

    def test_open_node_with_closed_parent(self) -> None:
        child = PDOutlineItem()
        child.add_last(PDOutlineItem())
        child.add_last(PDOutlineItem())
        self.root.add_last(child)
        assert self.root.get_open_count() == -1
        assert child.get_open_count() == -2
        child.open_node()
        assert self.root.get_open_count() == -3
        assert child.get_open_count() == 2

    # ---- add_last / add_first single child ----

    def test_add_last_single_child(self) -> None:
        child = PDOutlineItem()
        self.root.add_last(child)
        assert self.root.get_first_child() == child
        assert self.root.get_last_child() == child

    def test_add_first_single_child(self) -> None:
        child = PDOutlineItem()
        self.root.add_first(child)
        assert self.root.get_first_child() == child
        assert self.root.get_last_child() == child

    # ---- add_last + open child / open parent matrix ----

    def test_add_last_open_child_to_open_parent(self) -> None:
        child = PDOutlineItem()
        child.add_last(PDOutlineItem())
        child.add_last(PDOutlineItem())
        child.open_node()
        self.root.add_last(PDOutlineItem())
        self.root.open_node()
        assert self.root.get_open_count() == 1
        assert child.get_open_count() == 2
        self.root.add_last(child)
        assert self.root.get_first_child() != child
        assert self.root.get_last_child() == child
        assert self.root.get_open_count() == 4

    def test_add_first_open_child_to_open_parent(self) -> None:
        child = PDOutlineItem()
        child.add_first(PDOutlineItem())
        child.add_first(PDOutlineItem())
        child.open_node()
        self.root.add_first(PDOutlineItem())
        self.root.open_node()
        assert self.root.get_open_count() == 1
        assert child.get_open_count() == 2
        self.root.add_first(child)
        assert self.root.get_last_child() != child
        assert self.root.get_first_child() == child
        assert self.root.get_open_count() == 4

    def test_add_last_open_child_to_closed_parent(self) -> None:
        child = PDOutlineItem()
        child.add_last(PDOutlineItem())
        child.add_last(PDOutlineItem())
        child.open_node()
        self.root.add_last(PDOutlineItem())
        assert self.root.get_open_count() == -1
        assert child.get_open_count() == 2
        self.root.add_last(child)
        assert self.root.get_first_child() != child
        assert self.root.get_last_child() == child
        assert self.root.get_open_count() == -4

    def test_add_first_open_child_to_closed_parent(self) -> None:
        child = PDOutlineItem()
        child.add_first(PDOutlineItem())
        child.add_first(PDOutlineItem())
        child.open_node()
        self.root.add_first(PDOutlineItem())
        assert self.root.get_open_count() == -1
        assert child.get_open_count() == 2
        self.root.add_first(child)
        assert self.root.get_last_child() != child
        assert self.root.get_first_child() == child
        assert self.root.get_open_count() == -4

    def test_add_last_closed_child_to_open_parent(self) -> None:
        child = PDOutlineItem()
        child.add_last(PDOutlineItem())
        child.add_last(PDOutlineItem())
        self.root.add_last(PDOutlineItem())
        self.root.open_node()
        assert self.root.get_open_count() == 1
        assert child.get_open_count() == -2
        self.root.add_last(child)
        assert self.root.get_first_child() != child
        assert self.root.get_last_child() == child
        assert self.root.get_open_count() == 2

    def test_add_first_closed_child_to_open_parent(self) -> None:
        child = PDOutlineItem()
        child.add_first(PDOutlineItem())
        child.add_first(PDOutlineItem())
        self.root.add_first(PDOutlineItem())
        self.root.open_node()
        assert self.root.get_open_count() == 1
        assert child.get_open_count() == -2
        self.root.add_first(child)
        assert self.root.get_last_child() != child
        assert self.root.get_first_child() == child
        assert self.root.get_open_count() == 2

    def test_add_last_closed_child_to_closed_parent(self) -> None:
        child = PDOutlineItem()
        child.add_last(PDOutlineItem())
        child.add_last(PDOutlineItem())
        self.root.add_last(PDOutlineItem())
        assert self.root.get_open_count() == -1
        assert child.get_open_count() == -2
        self.root.add_last(child)
        assert self.root.get_first_child() != child
        assert self.root.get_last_child() == child
        assert self.root.get_open_count() == -2

    def test_add_first_closed_child_to_closed_parent(self) -> None:
        child = PDOutlineItem()
        child.add_first(PDOutlineItem())
        child.add_first(PDOutlineItem())
        self.root.add_first(PDOutlineItem())
        assert self.root.get_open_count() == -1
        assert child.get_open_count() == -2
        self.root.add_first(child)
        assert self.root.get_last_child() != child
        assert self.root.get_first_child() == child
        assert self.root.get_open_count() == -2

    # ---- require_single_node guard ----

    def test_cannot_add_last_a_list(self) -> None:
        child = PDOutlineItem()
        child.insert_sibling_after(PDOutlineItem())
        child.insert_sibling_after(PDOutlineItem())
        with pytest.raises(ValueError):
            self.root.add_last(child)

    def test_cannot_add_first_a_list(self) -> None:
        child = PDOutlineItem()
        child.insert_sibling_after(PDOutlineItem())
        child.insert_sibling_after(PDOutlineItem())
        with pytest.raises(ValueError):
            self.root.add_first(child)

    # ---- equality of fresh wrappers around the same dictionary ----

    def test_equals_node(self) -> None:
        self.root.add_first(PDOutlineItem())
        assert self.root.get_first_child() == self.root.get_last_child()

    # ---- children() iteration ----

    def test_iterator(self) -> None:
        first = PDOutlineItem()
        self.root.add_first(first)
        self.root.add_last(PDOutlineItem())
        second = PDOutlineItem()
        first.insert_sibling_after(second)
        counter = 0
        for _current in self.root.children():
            counter += 1
        assert counter == 3

    def test_iterator_no_children(self) -> None:
        # Upstream typo carried through (``iteratorNoChildre``) — kept the
        # corrected snake_case here.
        counter = 0
        for _current in PDOutlineItem().children():
            counter += 1
        assert counter == 0

    # ``open_node_and_append`` upstream is empty (``// TODO``) — skipped.
