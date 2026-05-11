"""Tests for :class:`Node` and :class:`Tree`."""

from __future__ import annotations

import pytest

from pypdfbox.filter import Node, Tree


class TestNode:
    def test_default_state(self) -> None:
        n = Node()
        assert n.left is None
        assert n.right is None
        assert n.value == 0
        assert n.can_be_fill is False
        assert n.is_leaf is False

    def test_set_left_right(self) -> None:
        parent = Node()
        lhs = Node()
        rhs = Node()
        parent.set(False, lhs)
        parent.set(True, rhs)
        assert parent.left is lhs
        assert parent.right is rhs

    def test_walk(self) -> None:
        parent = Node()
        lhs = Node()
        rhs = Node()
        parent.set(False, lhs)
        parent.set(True, rhs)
        assert parent.walk(False) is lhs
        assert parent.walk(True) is rhs

    def test_walk_missing_returns_none(self) -> None:
        n = Node()
        assert n.walk(True) is None
        assert n.walk(False) is None

    def test_repr_format(self) -> None:
        n = Node()
        n.value = 7
        n.is_leaf = True
        n.can_be_fill = True
        repr_s = repr(n)
        assert "leaf=True" in repr_s
        assert "value=7" in repr_s
        assert "canBeFill=True" in repr_s


class TestTree:
    def test_root_is_node(self) -> None:
        t = Tree()
        assert isinstance(t.root, Node)

    def test_fill_inserts_leaf(self) -> None:
        t = Tree()
        t.fill(3, 0b101, 42)
        # walk: 1 → right, 0 → left, 1 → right
        node = t.root.walk(True)
        assert node is not None
        node = node.walk(False)
        assert node is not None
        node = node.walk(True)
        assert node is not None
        assert node.is_leaf
        assert node.value == 42

    def test_fill_with_node_object(self) -> None:
        t = Tree()
        target = Node()
        target.value = 99
        target.is_leaf = True
        t.fill(2, 0b11, target)
        leaf = t.root.walk(True).walk(True)  # type: ignore[union-attr]
        assert leaf is target
        assert leaf.value == 99

    def test_fill_marks_can_be_fill_on_zero_path(self) -> None:
        t = Tree()
        t.fill(3, 0, 0)
        # All-left chain should have can_be_fill markers
        node = t.root.walk(False)
        assert node is not None
        assert node.can_be_fill is True

    def test_fill_conflicting_leaf_raises(self) -> None:
        t = Tree()
        t.fill(2, 0b11, 1)
        # Try to extend past an existing leaf
        with pytest.raises(OSError):
            t.fill(3, 0b111, 2)
