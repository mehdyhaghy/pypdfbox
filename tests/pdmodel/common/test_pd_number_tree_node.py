from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NUMS = COSName.get_pdf_name("Nums")
_LIMITS = COSName.get_pdf_name("Limits")


class _IntNumberTreeNode(PDNumberTreeNode[int]):
    """Concrete int-valued node for exercising the abstract base."""

    def convert_cos_to_value(self, base: COSBase) -> int:
        if not isinstance(base, COSInteger):
            raise OSError(f"Expected COSInteger, got {type(base).__name__}")
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNumberTreeNode:
        return _IntNumberTreeNode(dic)


def test_flat_numbers_round_trip() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 100, 2: 200, 3: 300})

    numbers = tree.get_numbers()
    assert numbers == {1: 100, 2: 200, 3: 300}
    assert tree.get_value(1) == 100
    assert tree.get_value(2) == 200
    assert tree.get_value(99) is None


def test_set_numbers_sorts_keys_in_array() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({30: 3, 10: 1, 20: 2})

    arr = tree.get_cos_object().get_dictionary_object(_NUMS)
    assert isinstance(arr, COSArray)
    keys = [arr.get_object(i).value for i in range(0, arr.size(), 2)]
    assert keys == [10, 20, 30]


def test_get_value_walks_kids_via_limits() -> None:
    leaf_one = _IntNumberTreeNode()
    leaf_one.set_numbers({1: 11, 2: 22})

    leaf_two = _IntNumberTreeNode()
    leaf_two.set_numbers({100: 1100, 200: 2200})

    root = _IntNumberTreeNode()
    root.set_kids([leaf_one, leaf_two])

    # Root carries only /Kids, not /Nums.
    assert root.get_cos_object().get_dictionary_object(_NUMS) is None
    assert isinstance(root.get_cos_object().get_dictionary_object(_KIDS), COSArray)

    assert root.get_value(1) == 11
    assert root.get_value(2) == 22
    assert root.get_value(100) == 1100
    assert root.get_value(200) == 2200
    # Out of range -> None
    assert root.get_value(50) is None
    assert root.get_value(9999) is None


def test_get_numbers_flattens_nested_kids() -> None:
    leaf_one = _IntNumberTreeNode()
    leaf_one.set_numbers({1: 11, 2: 22})

    leaf_two = _IntNumberTreeNode()
    leaf_two.set_numbers({100: 1100})

    intermediate = _IntNumberTreeNode()
    intermediate.set_kids([leaf_two])

    root = _IntNumberTreeNode()
    root.set_kids([leaf_one, intermediate])

    assert root.get_numbers() == {1: 11, 2: 22, 100: 1100}
    assert root.get_value(100) == 1100
    assert intermediate.get_lower_limit() == 100
    assert intermediate.get_upper_limit() == 100


def test_kids_set_parent_and_carry_limits() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({5: 50, 10: 100})

    root = _IntNumberTreeNode()
    root.set_kids([leaf])

    kids = root.get_kids()
    assert kids is not None and len(kids) == 1
    assert kids[0].get_cos_object() is leaf.get_cos_object()
    assert leaf.get_parent() is root
    assert leaf.is_root_node() is False
    assert root.is_root_node() is True
    # Root must not carry /Limits.
    assert root.get_cos_object().get_dictionary_object(_LIMITS) is None
    assert leaf.get_lower_limit() == 5
    assert leaf.get_upper_limit() == 10


def test_read_kids_are_parented_and_can_refresh_limits() -> None:
    leaf_dict = COSDictionary()
    nums = COSArray()
    nums.add(COSInteger.get(3))
    nums.add(COSInteger.get(30))
    leaf_dict.set_item(_NUMS, nums)

    root_dict = COSDictionary()
    kids = COSArray()
    kids.add(leaf_dict)
    root_dict.set_item(_KIDS, kids)

    root = _IntNumberTreeNode(root_dict)
    wrapped_kids = root.get_kids()
    assert wrapped_kids is not None
    child = wrapped_kids[0]

    assert child.get_parent() is root
    child.set_numbers({5: 50, 9: 90})
    assert child.get_lower_limit() == 5
    assert child.get_upper_limit() == 9


def test_lower_upper_limit_round_trip() -> None:
    parent = _IntNumberTreeNode()
    leaf = _IntNumberTreeNode()
    leaf.set_parent(parent)

    leaf.set_lower_limit(7)
    leaf.set_upper_limit(42)
    assert leaf.get_lower_limit() == 7
    assert leaf.get_upper_limit() == 42

    arr = leaf.get_cos_object().get_dictionary_object(_LIMITS)
    assert isinstance(arr, COSArray)
    assert arr.size() == 2


def test_set_numbers_none_clears_entries() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 100})
    tree.set_numbers(None)
    assert tree.get_numbers() is None
    assert tree.get_cos_object().get_dictionary_object(_NUMS) is None
    assert tree.get_cos_object().get_dictionary_object(_LIMITS) is None


def test_set_kids_empty_clears_entries() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({1: 1})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])

    root.set_kids(None)
    assert root.get_kids() is None
    assert root.get_cos_object().get_dictionary_object(_KIDS) is None


def test_get_numbers_none_when_only_kids() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({1: 1})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])
    assert root.get_numbers() == {1: 1}
    assert root.get_kids() is not None


def test_get_kids_none_when_only_numbers() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 1})
    assert tree.get_kids() is None


def test_get_numbers_rejects_non_integer_key() -> None:
    tree = _IntNumberTreeNode()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("NotANumber"))
    arr.add(COSInteger.get(1))
    tree.get_cos_object().set_item(_NUMS, arr)
    # Upstream behavior: returns None on bad key (logs error).
    assert tree.get_numbers() is None


def test_large_root_numbers_write_as_deterministic_kids() -> None:
    tree = _IntNumberTreeNode()
    numbers = {key: key * 10 for key in range(130, 0, -1)}
    tree.set_numbers(numbers)

    assert tree.get_cos_object().get_dictionary_object(_NUMS) is None
    kids = tree.get_kids()
    assert kids is not None
    assert len(kids) == 3
    assert [kid.get_lower_limit() for kid in kids] == [1, 65, 129]
    assert [kid.get_upper_limit() for kid in kids] == [64, 128, 130]
    assert tree.get_numbers() == {key: key * 10 for key in range(1, 131)}
    assert tree.get_value(130) == 1300

    first_nums = kids[0].get_cos_object().get_dictionary_object(_NUMS)
    assert isinstance(first_nums, COSArray)
    first_keys = [first_nums.get_object(i).value for i in range(0, first_nums.size(), 2)]
    assert first_keys == list(range(1, 65))


def test_create_child_node_returns_same_type() -> None:
    tree = _IntNumberTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, _IntNumberTreeNode)


def test_pd_number_tree_node_is_abstract() -> None:
    with pytest.raises(TypeError):
        PDNumberTreeNode()  # type: ignore[abstract]
