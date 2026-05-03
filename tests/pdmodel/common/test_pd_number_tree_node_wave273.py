"""Wave 273 round-out tests for PDNumberTreeNode cold gaps.

Targets the predicates and ``clear`` helpers that were missing in
parity with :class:`PDNameTreeNode`."""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NUMS = COSName.get_pdf_name("Nums")
_LIMITS = COSName.get_pdf_name("Limits")


class _IntNumberTreeNode(PDNumberTreeNode[int]):
    def convert_cos_to_value(self, base: COSBase) -> int:
        if not isinstance(base, COSInteger):
            raise OSError(f"Expected COSInteger, got {type(base).__name__}")
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNumberTreeNode:
        return _IntNumberTreeNode(dic)


# ---------- has_limits predicate ----------


def test_has_limits_false_on_empty_node() -> None:
    tree = _IntNumberTreeNode()
    assert tree.has_limits() is False


def test_has_limits_false_on_root_node_with_numbers() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10, 2: 20})
    # Root nodes never carry /Limits.
    assert tree.has_limits() is False


def test_has_limits_true_on_leaf_with_parent() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({5: 50, 10: 100})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])
    assert leaf.has_limits() is True
    # Root still has none.
    assert root.has_limits() is False


def test_has_limits_clears_after_remove_numbers() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({5: 50})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])
    assert leaf.has_limits() is True
    leaf.remove_numbers()
    assert leaf.has_limits() is False


# ---------- is_leaf_node / is_intermediate_node predicates ----------


def test_is_leaf_node_true_when_only_numbers() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10})
    assert tree.is_leaf_node() is True
    assert tree.is_intermediate_node() is False


def test_is_intermediate_node_true_when_only_kids() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({1: 10})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])

    assert root.is_intermediate_node() is True
    assert root.is_leaf_node() is False


def test_empty_node_is_neither_leaf_nor_intermediate() -> None:
    tree = _IntNumberTreeNode()
    assert tree.is_leaf_node() is False
    assert tree.is_intermediate_node() is False


def test_predicates_track_after_clear() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10})
    assert tree.is_leaf_node() is True
    tree.clear()
    assert tree.is_leaf_node() is False
    assert tree.is_intermediate_node() is False


def test_predicates_track_set_kids_then_set_numbers() -> None:
    """Switching shape must flip the predicates atomically — set_numbers
    on the root replaces /Kids with /Nums per the upstream contract."""
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({1: 10})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])
    assert root.is_intermediate_node() is True

    root.set_numbers({100: 1000})
    assert root.is_leaf_node() is True
    assert root.is_intermediate_node() is False


# ---------- clear() ----------


def test_clear_drops_numbers_and_limits() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10, 2: 20})
    tree.clear()
    assert tree.get_cos_object().get_dictionary_object(_NUMS) is None
    assert tree.get_cos_object().get_dictionary_object(_KIDS) is None
    assert tree.get_cos_object().get_dictionary_object(_LIMITS) is None
    assert tree.get_numbers() is None


def test_clear_drops_kids_and_limits() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({1: 10})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])

    root.clear()
    assert root.get_cos_object().get_dictionary_object(_NUMS) is None
    assert root.get_cos_object().get_dictionary_object(_KIDS) is None
    assert root.get_cos_object().get_dictionary_object(_LIMITS) is None


def test_clear_on_empty_node_is_noop() -> None:
    tree = _IntNumberTreeNode()
    tree.clear()  # must not raise
    assert tree.get_cos_object().get_dictionary_object(_NUMS) is None
    assert tree.get_cos_object().get_dictionary_object(_KIDS) is None
    assert tree.get_cos_object().get_dictionary_object(_LIMITS) is None


def test_clear_drops_only_relevant_keys() -> None:
    """``clear`` must not touch unrelated dictionary entries — number-tree
    nodes can carry application-specific keys at the same level
    (e.g. ``/Type``)."""
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10})
    tree.get_cos_object().set_name(COSName.TYPE, "Nums")  # type: ignore[attr-defined]

    tree.clear()
    assert tree.get_cos_object().get_dictionary_object(_NUMS) is None
    assert tree.get_cos_object().get_dictionary_object(_LIMITS) is None
    type_value = tree.get_cos_object().get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
    assert isinstance(type_value, COSName)
    assert type_value.get_name() == "Nums"


def test_clear_on_leaf_notifies_parent() -> None:
    """Clearing a non-root leaf must trigger the parent-limits walk so
    intermediate ancestors recompute their /Limits."""
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({5: 50, 10: 100})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])

    leaf.clear()
    # Leaf has nothing → no /Limits.
    assert leaf.get_lower_limit() is None
    assert leaf.get_upper_limit() is None
