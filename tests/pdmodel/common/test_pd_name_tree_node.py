from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NAMES = COSName.get_pdf_name("Names")
_LIMITS = COSName.get_pdf_name("Limits")


def test_flat_names_round_trip() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "alpha", "b": "beta"})

    names = tree.get_names()
    assert names == {"a": "alpha", "b": "beta"}
    assert tree.get_value("a") == "alpha"
    assert tree.get_value("b") == "beta"
    assert tree.get_value("missing") is None


def test_set_names_sorts_and_writes_cos_array() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"banana": "B", "apple": "A", "cherry": "C"})

    arr = tree.get_cos_object().get_dictionary_object(_NAMES)
    assert isinstance(arr, COSArray)
    keys = [arr.get_object(i).get_string() for i in range(0, arr.size(), 2)]
    assert keys == ["apple", "banana", "cherry"]


def test_get_value_walks_kids_via_limits() -> None:
    # Two leaf children, root has only /Kids.
    leaf_one = PDStringNameTreeNode()
    leaf_one.set_names({"alpha": "A1", "bravo": "A2"})

    leaf_two = PDStringNameTreeNode()
    leaf_two.set_names({"mike": "M1", "november": "M2"})

    root = PDStringNameTreeNode()
    root.set_kids([leaf_one, leaf_two])

    # Root should not carry /Names; only /Kids.
    assert root.get_cos_object().get_dictionary_object(_NAMES) is None
    assert isinstance(root.get_cos_object().get_dictionary_object(_KIDS), COSArray)

    # Walk into the second kid (limits-driven binary descent).
    assert root.get_value("mike") == "M1"
    assert root.get_value("november") == "M2"
    # Walk into the first kid as well.
    assert root.get_value("alpha") == "A1"
    # Name outside both kids' limit ranges still resolves to None.
    assert root.get_value("zulu") is None


def test_kids_carry_limits_and_parent_link() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"alpha": "A", "bravo": "B"})

    root = PDStringNameTreeNode()
    root.set_kids([leaf])

    kids = root.get_kids()
    assert kids is not None and len(kids) == 1
    # The stored child wrapper is freshly built by create_child_node, but
    # its underlying COSDictionary is the same one we put in.
    assert kids[0].get_cos_object() is leaf.get_cos_object()
    # Parent link was set on the original leaf during set_kids.
    assert leaf.get_parent() is root
    assert leaf.is_root_node() is False
    assert root.is_root_node() is True

    # Limits propagate from the only child to the root only when root is non-root;
    # the root itself must not carry /Limits.
    assert root.get_cos_object().get_dictionary_object(_LIMITS) is None
    assert leaf.get_lower_limit() == "alpha"
    assert leaf.get_upper_limit() == "bravo"


def test_lower_upper_limit_round_trip() -> None:
    # Construct a non-root node by attaching a parent so set_lower/upper_limit
    # actually persists into /Limits.
    parent = PDStringNameTreeNode()
    leaf = PDStringNameTreeNode()
    leaf.set_parent(parent)

    leaf.set_lower_limit("aardvark")
    leaf.set_upper_limit("zebra")
    assert leaf.get_lower_limit() == "aardvark"
    assert leaf.get_upper_limit() == "zebra"

    arr = leaf.get_cos_object().get_dictionary_object(_LIMITS)
    assert isinstance(arr, COSArray)
    assert arr.size() == 2


def test_get_kids_none_when_only_names() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "A"})
    assert tree.get_kids() is None
    assert tree.get_names() == {"a": "A"}


def test_get_names_none_when_only_kids() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"x": "X"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])
    assert root.get_names() is None
    assert root.get_kids() is not None


def test_set_names_none_clears_entries() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "A"})
    tree.set_names(None)
    assert tree.get_names() is None
    assert tree.get_cos_object().get_dictionary_object(_NAMES) is None
    assert tree.get_cos_object().get_dictionary_object(_LIMITS) is None


def test_set_kids_empty_clears_entries() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])

    root.set_kids(None)
    assert root.get_kids() is None
    assert root.get_cos_object().get_dictionary_object(_KIDS) is None


def test_get_names_rejects_non_string_key() -> None:
    tree = PDStringNameTreeNode()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("NotAString"))
    arr.add(COSString("value"))
    tree.get_cos_object().set_item(_NAMES, arr)
    with pytest.raises(OSError):
        tree.get_names()


def test_string_name_tree_create_child_node_returns_same_type() -> None:
    tree = PDStringNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDStringNameTreeNode)


def test_pd_name_tree_node_is_abstract() -> None:
    with pytest.raises(TypeError):
        PDNameTreeNode()  # type: ignore[abstract]
