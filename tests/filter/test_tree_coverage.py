"""Coverage tests for :mod:`pypdfbox.filter.tree`.

The wave 1280 baseline didn't exercise the parity-stub debugger-UI
methods (lines 78-118) — they raise ``NotImplementedError`` because the
Swing-based debugger UI isn't ported. These tests pin that behaviour.
"""

from __future__ import annotations

import pytest

from pypdfbox.filter.node import Node
from pypdfbox.filter.tree import Tree


@pytest.fixture()
def tree() -> Tree:
    return Tree()


def test_add_popup_menu_items_raises_not_implemented(tree: Tree) -> None:
    with pytest.raises(NotImplementedError):
        tree.add_popup_menu_items(node_path=None)


def test_get_file_extension_for_stream_raises_not_implemented(tree: Tree) -> None:
    with pytest.raises(NotImplementedError):
        tree.get_file_extension_for_stream(cos_stream=None, node_path=None)


def test_get_file_open_menu_raises_not_implemented(tree: Tree) -> None:
    with pytest.raises(NotImplementedError):
        tree.get_file_open_menu(cos_stream=None, node_path=None)


def test_get_filters_raises_not_implemented(tree: Tree) -> None:
    with pytest.raises(NotImplementedError):
        tree.get_filters(cos_stream=None)


def test_get_partial_stream_saving_menu_item_raises_not_implemented(
    tree: Tree,
) -> None:
    with pytest.raises(NotImplementedError):
        tree.get_partial_stream_saving_menu_item(
            index_of_stop_filter=0, stream=None
        )


def test_get_partially_decoded_stream_save_menu_raises_not_implemented(
    tree: Tree,
) -> None:
    with pytest.raises(NotImplementedError):
        tree.get_partially_decoded_stream_save_menu(cos_stream=None)


def test_get_popup_location_raises_not_implemented(tree: Tree) -> None:
    with pytest.raises(NotImplementedError):
        tree.get_popup_location(event=None)


def test_get_raw_stream_save_menu_raises_not_implemented(tree: Tree) -> None:
    with pytest.raises(NotImplementedError):
        tree.get_raw_stream_save_menu(cos_stream=None)


def test_get_stream_save_menu_raises_not_implemented(tree: Tree) -> None:
    with pytest.raises(NotImplementedError):
        tree.get_stream_save_menu(cos_stream=None, node_path=None)


def test_get_tree_path_menu_item_raises_not_implemented(tree: Tree) -> None:
    with pytest.raises(NotImplementedError):
        tree.get_tree_path_menu_item(path=None)


def test_save_stream_raises_not_implemented(tree: Tree) -> None:
    with pytest.raises(NotImplementedError):
        tree.save_stream(data=b"", file_filter=None, extension=".bin")


# ----------------------------------------------------------------------
# fill() — Huffman insertion semantics (lines 37-64)
# ----------------------------------------------------------------------
def test_fill_inserts_leaf_at_target_depth(tree: Tree) -> None:
    """Inserting a 3-bit code 0b101 must create a leaf at depth 3
    carrying the integer value, reachable by right-left-right walk.
    """
    tree.fill(depth=3, path=0b101, value_or_node=42)
    # Walk r-l-r from the root.
    n1 = tree.root.walk(True)
    assert n1 is not None and not n1.is_leaf
    n2 = n1.walk(False)
    assert n2 is not None and not n2.is_leaf
    leaf = n2.walk(True)
    assert leaf is not None and leaf.is_leaf
    assert leaf.value == 42


def test_fill_marks_can_be_fill_for_all_zero_path(tree: Tree) -> None:
    """The all-zero path (used for fill bits before EOL) sets
    ``can_be_fill=True`` on each freshly created node along that path.
    """
    tree.fill(depth=2, path=0, value_or_node=0)
    left = tree.root.walk(False)
    assert left is not None
    assert left.can_be_fill is True
    leaf = left.walk(False)
    assert leaf is not None
    assert leaf.is_leaf
    assert leaf.can_be_fill is True


def test_fill_accepts_prebuilt_node_at_leaf_position(tree: Tree) -> None:
    """Passing a ``Node`` (rather than ``int``) splices that node at
    ``depth`` instead of creating a new leaf — exercises the
    ``is_node`` branch.
    """
    custom = Node()
    custom.value = 99
    custom.is_leaf = True
    tree.fill(depth=2, path=0b10, value_or_node=custom)
    leaf = tree.root.walk(True).walk(False)  # type: ignore[union-attr]
    assert leaf is custom


def test_fill_raises_oserror_when_intermediate_is_already_leaf(tree: Tree) -> None:
    """If an intermediate node along the path is already a leaf, ``fill``
    raises ``OSError('node is leaf, no other following')`` — Java
    ``IOException`` equivalent.
    """
    tree.fill(depth=1, path=0b1, value_or_node=7)  # leaf at root.right
    with pytest.raises(OSError, match="node is leaf"):
        tree.fill(depth=2, path=0b10, value_or_node=8)


def test_fill_reuses_existing_intermediate_node(tree: Tree) -> None:
    """Two codes that share a prefix must reuse the shared intermediate
    nodes rather than overwriting them — exercises the ``next_node is
    not None`` branch where the existing child is reused.
    """
    tree.fill(depth=3, path=0b110, value_or_node=5)
    tree.fill(depth=3, path=0b111, value_or_node=6)
    # root.right -> right -> {left=5, right=6}.
    n1 = tree.root.walk(True)
    assert n1 is not None
    n2 = n1.walk(True)
    assert n2 is not None
    assert n2.walk(False).value == 5  # type: ignore[union-attr]
    assert n2.walk(True).value == 6  # type: ignore[union-attr]
