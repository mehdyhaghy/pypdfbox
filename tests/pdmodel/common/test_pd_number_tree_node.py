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


def _number_tree_keys(arr: COSArray) -> list[int]:
    keys: list[int] = []
    for i in range(0, arr.size(), 2):
        key = arr.get_object(i)
        assert isinstance(key, COSInteger)
        keys.append(int(key.value))
    return keys


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
    assert _number_tree_keys(arr) == [10, 20, 30]


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
    assert _number_tree_keys(first_nums) == list(range(1, 65))


def test_create_child_node_returns_same_type() -> None:
    tree = _IntNumberTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, _IntNumberTreeNode)


def test_pd_number_tree_node_is_abstract() -> None:
    with pytest.raises(TypeError):
        PDNumberTreeNode()  # type: ignore[abstract]


def test_get_number_aliases_get_value() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10, 2: 20, 3: 30})
    assert tree.get_number(2) == 20
    assert tree.get_number(99) is None
    # Must walk through kids identically to get_value().
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({100: 1000})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])
    assert root.get_number(100) == 1000
    assert root.get_value(100) == root.get_number(100)


def test_factory_value_typing_via_subclass() -> None:
    # The factory subclass narrows the value type — convert_cos_to_value
    # must reject the wrong COS type.
    tree = _IntNumberTreeNode()
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSName.get_pdf_name("NotAnInt"))
    tree.get_cos_object().set_item(_NUMS, arr)
    with pytest.raises(OSError):
        tree.get_numbers()


def test_set_kids_replaces_existing_numbers_on_root() -> None:
    root = _IntNumberTreeNode()
    root.set_numbers({1: 1, 2: 2})
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({10: 100})
    root.set_kids([leaf])
    # Root with /Kids must drop /Nums per spec.
    assert root.get_cos_object().get_dictionary_object(_NUMS) is None
    assert root.get_value(10) == 100


def test_set_kids_replaces_existing_numbers_on_non_root() -> None:
    parent = _IntNumberTreeNode()
    parent.set_numbers({1: 10})
    root = _IntNumberTreeNode()
    root.set_kids([parent])

    leaf = _IntNumberTreeNode()
    leaf.set_numbers({20: 200})
    parent.set_kids([leaf])

    assert parent.get_cos_object().get_dictionary_object(_NUMS) is None
    assert parent.is_intermediate_node() is True
    assert parent.get_numbers() == {20: 200}
    assert root.get_value(20) == 200


def test_set_kids_on_non_root_refreshes_ancestor_limits() -> None:
    parent = _IntNumberTreeNode()
    parent.set_numbers({1: 10})
    middle = _IntNumberTreeNode()
    middle.set_kids([parent])
    root = _IntNumberTreeNode()
    root.set_kids([middle])

    leaf = _IntNumberTreeNode()
    leaf.set_numbers({50: 500})
    parent.set_kids([leaf])

    assert middle.get_lower_limit() == 50
    assert middle.get_upper_limit() == 50
    assert root.get_value(50) == 500


def test_lower_upper_limit_can_be_cleared() -> None:
    parent = _IntNumberTreeNode()
    leaf = _IntNumberTreeNode()
    leaf.set_parent(parent)
    leaf.set_lower_limit(7)
    leaf.set_upper_limit(42)
    leaf.set_lower_limit(None)
    leaf.set_upper_limit(None)
    assert leaf.get_lower_limit() is None
    assert leaf.get_upper_limit() is None


# ---------- round-out: get_number_of_values + __contains__ parity ----------


def test_get_number_of_values_flat_and_nested() -> None:
    flat = _IntNumberTreeNode()
    flat.set_numbers({1: 10, 2: 20, 3: 30})
    assert flat.get_number_of_values() == 3

    leaf_one = _IntNumberTreeNode()
    leaf_one.set_numbers({1: 10, 2: 20})
    leaf_two = _IntNumberTreeNode()
    leaf_two.set_numbers({100: 1000})
    root = _IntNumberTreeNode()
    root.set_kids([leaf_one, leaf_two])
    assert root.get_number_of_values() == 3

    empty = _IntNumberTreeNode()
    assert empty.get_number_of_values() == 0


def test_get_number_of_values_recurses_through_intermediate_kids() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({1: 1, 2: 2, 3: 3})
    intermediate = _IntNumberTreeNode()
    intermediate.set_kids([leaf])
    root = _IntNumberTreeNode()
    root.set_kids([intermediate])
    assert root.get_number_of_values() == 3


def test_contains_operator_walks_tree() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({5: 50, 10: 100})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])

    assert 5 in root
    assert 10 in root
    assert 7 not in root
    # Non-int keys (including bool, which subclasses int) are rejected.
    assert "5" not in root
    assert True not in root


def test_contains_operator_on_flat_node() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10, 2: 20})
    assert 1 in tree
    assert 2 in tree
    assert 99 not in tree


# ---------- Wave 197 round-out: predicates, value_type, remove_*, merge ----------


def test_has_numbers_predicate() -> None:
    flat = _IntNumberTreeNode()
    assert flat.has_numbers() is False
    flat.set_numbers({1: 10})
    assert flat.has_numbers() is True
    flat.set_numbers(None)
    assert flat.has_numbers() is False


def test_has_kids_predicate() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({1: 10})
    root = _IntNumberTreeNode()
    assert root.has_kids() is False
    root.set_kids([leaf])
    assert root.has_kids() is True
    # When the root carries /Kids, /Nums must be absent (already exercised
    # elsewhere) and has_numbers should reflect it.
    assert root.has_numbers() is False


def test_has_predicates_independent_of_each_other() -> None:
    # An empty fresh node has neither /Kids nor /Nums.
    empty = _IntNumberTreeNode()
    assert empty.has_kids() is False
    assert empty.has_numbers() is False


def test_get_value_type_default_is_none() -> None:
    tree = _IntNumberTreeNode()
    # Default ctor never passes ``value_type`` → exposed as None.
    assert tree.get_value_type() is None


def test_get_value_type_round_trip() -> None:
    class _Marker:
        pass

    tree = _IntNumberTreeNode(value_type=_Marker)
    assert tree.get_value_type() is _Marker


def test_remove_numbers_clears_entries() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10, 2: 20})
    assert tree.has_numbers() is True
    tree.remove_numbers()
    assert tree.has_numbers() is False
    assert tree.get_cos_object().get_dictionary_object(_NUMS) is None
    assert tree.get_cos_object().get_dictionary_object(_LIMITS) is None
    # Calling on an already-empty node must be a no-op.
    tree.remove_numbers()
    assert tree.has_numbers() is False


def test_remove_kids_clears_entries() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({1: 10})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])
    assert root.has_kids() is True
    root.remove_kids()
    assert root.has_kids() is False
    assert root.get_cos_object().get_dictionary_object(_KIDS) is None
    assert root.get_cos_object().get_dictionary_object(_LIMITS) is None


def test_remove_numbers_notifies_parent() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({5: 50, 10: 100})
    root = _IntNumberTreeNode()
    root.set_kids([leaf])
    # Parent picks up leaf's limits via _calculate_limits chain.
    assert leaf.get_lower_limit() == 5
    assert leaf.get_upper_limit() == 10

    leaf.remove_numbers()
    # After removing leaf's numbers, the leaf's own /Limits is gone.
    assert leaf.get_lower_limit() is None
    assert leaf.get_upper_limit() is None


def test_merge_with_dict_combines_values() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10, 2: 20})
    tree.merge({3: 30, 4: 40})
    assert tree.get_numbers() == {1: 10, 2: 20, 3: 30, 4: 40}


def test_merge_with_other_node_combines_values() -> None:
    a = _IntNumberTreeNode()
    a.set_numbers({1: 10, 2: 20})

    b = _IntNumberTreeNode()
    b.set_numbers({3: 30, 4: 40})

    a.merge(b)
    assert a.get_numbers() == {1: 10, 2: 20, 3: 30, 4: 40}


def test_merge_overwrites_on_key_collision() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10, 2: 20})
    tree.merge({2: 999, 3: 30})
    assert tree.get_numbers() == {1: 10, 2: 999, 3: 30}


def test_merge_none_is_noop() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10})
    tree.merge(None)
    assert tree.get_numbers() == {1: 10}


def test_merge_empty_dict_is_noop() -> None:
    tree = _IntNumberTreeNode()
    tree.set_numbers({1: 10})
    tree.merge({})
    assert tree.get_numbers() == {1: 10}


def test_merge_into_empty_node() -> None:
    tree = _IntNumberTreeNode()
    tree.merge({1: 10, 2: 20})
    assert tree.get_numbers() == {1: 10, 2: 20}


def test_merge_rebalances_into_kids_above_threshold() -> None:
    # Merging in enough entries to cross _MAX_NUMS (64) flips the root
    # from leaf-shape to kids-shape, mirroring set_numbers behaviour.
    tree = _IntNumberTreeNode()
    tree.set_numbers({i: i * 10 for i in range(40)})
    tree.merge({i: i * 10 for i in range(40, 130)})
    # Root must now be in kids-shape.
    assert tree.has_numbers() is False
    assert tree.has_kids() is True
    assert tree.get_numbers() == {i: i * 10 for i in range(130)}
