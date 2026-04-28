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
    assert root.get_names() == {"x": "X"}
    assert root.get_kids() is not None


def test_get_names_reads_nested_kids() -> None:
    leaf_one = PDStringNameTreeNode()
    leaf_one.set_names({"alpha": "A", "bravo": "B"})
    leaf_two = PDStringNameTreeNode()
    leaf_two.set_names({"charlie": "C"})

    middle = PDStringNameTreeNode()
    middle.set_kids([leaf_one, leaf_two])

    leaf_three = PDStringNameTreeNode()
    leaf_three.set_names({"delta": "D"})

    root = PDStringNameTreeNode()
    root.set_kids([middle, leaf_three])

    assert root.get_names() == {
        "alpha": "A",
        "bravo": "B",
        "charlie": "C",
        "delta": "D",
    }
    assert root.get_value("delta") == "D"


def test_get_kids_from_cos_sets_parent_without_rewriting_limits() -> None:
    child_dict = COSDictionary()
    child_limits = COSArray()
    child_limits.add(COSString("a"))
    child_limits.add(COSString("z"))
    child_dict.set_item(_LIMITS, child_limits)

    root_dict = COSDictionary()
    root_kids = COSArray()
    root_kids.add(child_dict)
    root_dict.set_item(_KIDS, root_kids)

    root = PDStringNameTreeNode(root_dict)
    kids = root.get_kids()

    assert kids is not None
    assert kids[0].get_parent() is root
    assert kids[0].get_lower_limit() == "a"
    assert kids[0].get_upper_limit() == "z"


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


def test_set_names_large_map_writes_kids_with_limits() -> None:
    tree = PDStringNameTreeNode()
    names = {f"k{i:03d}": f"v{i:03d}" for i in range(65)}

    tree.set_names(names)

    root_dict = tree.get_cos_object()
    assert root_dict.get_dictionary_object(_NAMES) is None
    assert root_dict.get_dictionary_object(_LIMITS) is None

    root_kids = root_dict.get_dictionary_object(_KIDS)
    assert isinstance(root_kids, COSArray)
    assert root_kids.size() == 2

    first = root_kids.get_object(0)
    second = root_kids.get_object(1)
    assert isinstance(first, COSDictionary)
    assert isinstance(second, COSDictionary)
    assert PDStringNameTreeNode(first).get_lower_limit() == "k000"
    assert PDStringNameTreeNode(first).get_upper_limit() == "k063"
    assert PDStringNameTreeNode(second).get_lower_limit() == "k064"
    assert PDStringNameTreeNode(second).get_upper_limit() == "k064"
    assert tree.get_names() == names


def test_set_names_large_map_has_deterministic_leaf_shape() -> None:
    tree = PDStringNameTreeNode()
    names = {f"k{i:03d}": f"v{i:03d}" for i in reversed(range(130))}

    tree.set_names(names)

    root_kids = tree.get_cos_object().get_dictionary_object(_KIDS)
    assert isinstance(root_kids, COSArray)
    assert root_kids.size() == 3

    leaf_sizes = []
    leaf_bounds = []
    for i in range(root_kids.size()):
        leaf = root_kids.get_object(i)
        assert isinstance(leaf, COSDictionary)
        names_array = leaf.get_dictionary_object(_NAMES)
        assert isinstance(names_array, COSArray)
        leaf_sizes.append(names_array.size() // 2)
        leaf_bounds.append(
            (
                PDStringNameTreeNode(leaf).get_lower_limit(),
                PDStringNameTreeNode(leaf).get_upper_limit(),
            )
        )

    assert leaf_sizes == [64, 64, 2]
    assert leaf_bounds == [("k000", "k063"), ("k064", "k127"), ("k128", "k129")]


def test_string_name_tree_create_child_node_returns_same_type() -> None:
    tree = PDStringNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDStringNameTreeNode)


def test_pd_name_tree_node_is_abstract() -> None:
    with pytest.raises(TypeError):
        PDNameTreeNode()  # type: ignore[abstract]


# ---------- round-out: value_type, remove_*, merge, sizing, contains ----------


def test_value_type_constructor_arg_round_trips() -> None:
    tree = PDStringNameTreeNode()
    assert tree.get_value_type() is None

    typed = PDStringNameTreeNode()
    # Subclasses pin T, but the base lets callers stash the marker class
    # for parity with PDFBox's ``PDNameTreeNode(Class<? extends T>)`` ctor.
    typed._value_type = str  # noqa: SLF001 - direct marker assignment is fine
    assert typed.get_value_type() is str


def test_remove_names_clears_only_names_and_limits() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "A", "b": "B"})

    tree.remove_names()

    assert tree.get_cos_object().get_dictionary_object(_NAMES) is None
    assert tree.get_cos_object().get_dictionary_object(_LIMITS) is None
    # /Kids was never present so still absent.
    assert tree.get_cos_object().get_dictionary_object(_KIDS) is None


def test_remove_kids_clears_kids_and_limits() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])

    root.remove_kids()
    assert root.get_cos_object().get_dictionary_object(_KIDS) is None
    assert root.get_cos_object().get_dictionary_object(_LIMITS) is None


def test_merge_with_dict_inserts_and_overwrites() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "A", "b": "B"})

    tree.merge({"b": "B2", "c": "C"})

    assert tree.get_names() == {"a": "A", "b": "B2", "c": "C"}


def test_merge_with_other_node_flattens_kids() -> None:
    leaf_one = PDStringNameTreeNode()
    leaf_one.set_names({"a": "A", "b": "B"})
    leaf_two = PDStringNameTreeNode()
    leaf_two.set_names({"y": "Y", "z": "Z"})
    other = PDStringNameTreeNode()
    other.set_kids([leaf_one, leaf_two])

    target = PDStringNameTreeNode()
    target.set_names({"m": "M"})
    target.merge(other)

    assert target.get_names() == {"a": "A", "b": "B", "m": "M", "y": "Y", "z": "Z"}


def test_merge_none_and_empty_are_noops() -> None:
    tree = PDStringNameTreeNode()
    tree.set_names({"a": "A"})

    tree.merge(None)
    tree.merge({})
    assert tree.get_names() == {"a": "A"}


def test_get_number_of_values_flat_and_nested() -> None:
    flat = PDStringNameTreeNode()
    flat.set_names({"a": "A", "b": "B", "c": "C"})
    assert flat.get_number_of_values() == 3

    leaf_one = PDStringNameTreeNode()
    leaf_one.set_names({"alpha": "A", "bravo": "B"})
    leaf_two = PDStringNameTreeNode()
    leaf_two.set_names({"charlie": "C"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf_one, leaf_two])
    assert root.get_number_of_values() == 3

    empty = PDStringNameTreeNode()
    assert empty.get_number_of_values() == 0


def test_contains_operator_walks_tree() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"alpha": "A"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])

    assert "alpha" in root
    assert "missing" not in root
    # Non-string types just return False instead of raising.
    assert 123 not in root  # type: ignore[operator]
