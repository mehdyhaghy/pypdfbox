"""Wave 273 round-out tests for PDNameTreeNode cold gaps.

Targets the ``has_*`` shape predicates that complement the existing
``is_leaf_node`` / ``is_intermediate_node`` semantics."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NAMES = COSName.get_pdf_name("Names")
_LIMITS = COSName.get_pdf_name("Limits")


# ---------- has_names predicate ----------


def test_has_names_false_on_empty_node() -> None:
    tree = PDStringNameTreeNode()
    assert tree.has_names() is False


def test_has_names_true_on_leaf() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "A", "b": "B"})
    assert tree.has_names() is True


def test_has_names_false_on_root_with_kids() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])
    # Root with /Kids must not carry /Names.
    assert root.has_names() is False


def test_has_names_clears_after_remove_names() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "A"})
    assert tree.has_names() is True
    tree.remove_names()
    assert tree.has_names() is False


# ---------- has_kids predicate ----------


def test_has_kids_false_on_empty_node() -> None:
    tree = PDStringNameTreeNode()
    assert tree.has_kids() is False


def test_has_kids_false_on_leaf() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "A"})
    assert tree.has_kids() is False


def test_has_kids_true_on_intermediate_node() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])
    assert root.has_kids() is True


def test_has_kids_clears_after_remove_kids() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])
    assert root.has_kids() is True
    root.remove_kids()
    assert root.has_kids() is False


# ---------- has_limits predicate ----------


def test_has_limits_false_on_empty_node() -> None:
    tree = PDStringNameTreeNode()
    assert tree.has_limits() is False


def test_has_limits_false_on_root_with_names() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "A"})
    # Root nodes never carry /Limits.
    assert tree.has_limits() is False


def test_has_limits_true_on_leaf_with_parent() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A", "z": "Z"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])
    assert leaf.has_limits() is True
    assert root.has_limits() is False


def test_has_limits_clears_after_remove_names() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])
    assert leaf.has_limits() is True
    leaf.remove_names()
    assert leaf.has_limits() is False


# ---------- predicate alignment with shape transitions ----------


def test_predicates_track_set_kids_then_set_names_on_root() -> None:
    """Switching root shape from intermediate → leaf must flip the
    has_names / has_kids predicates atomically; mirrors the upstream
    ``setKids``/``setNames`` mutual-exclusion contract."""
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])
    assert root.has_kids() is True
    assert root.has_names() is False

    # Switch root over to a leaf-shape via set_names.
    root.set_names({"x": "X"})
    assert root.has_names() is True
    # set_names always removes /Kids on the root, so:
    assert root.has_kids() is False


def test_has_predicates_independent_of_each_other() -> None:
    empty = PDStringNameTreeNode()
    assert empty.has_kids() is False
    assert empty.has_names() is False
    assert empty.has_limits() is False


# ---------- has_limits reads raw dictionary directly ----------


def test_has_limits_reflects_externally_set_array() -> None:
    """``has_limits`` must read the raw COS dictionary so callers can
    inspect parsed-from-disk shape before any wrapper-driven mutation."""
    raw = COSDictionary()
    limits = COSArray()
    limits.add(COSString("a"))
    limits.add(COSString("z"))
    raw.set_item(_LIMITS, limits)
    tree = PDStringNameTreeNode(raw)
    assert tree.has_limits() is True
