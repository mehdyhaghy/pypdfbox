"""Wave 297 regression tests for PDNumberTreeNode lookup hardening."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NUMS = COSName.get_pdf_name("Nums")


class _IntNumberTreeNode(PDNumberTreeNode[int]):
    def convert_cos_to_value(self, base: COSBase) -> int:
        if not isinstance(base, COSInteger):
            raise OSError(f"Expected COSInteger, got {type(base).__name__}")
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNumberTreeNode:
        return _IntNumberTreeNode(dic)


def _leaf_with_raw_nums(*items: COSBase) -> COSDictionary:
    leaf = COSDictionary()
    nums = COSArray()
    for item in items:
        nums.add(item)
    leaf.set_item(_NUMS, nums)
    return leaf


def test_get_value_uses_child_limits_without_flattening_siblings() -> None:
    first = _leaf_with_raw_nums(COSInteger.get(1), COSInteger.get(10))
    _IntNumberTreeNode(first).set_lower_limit(1)
    _IntNumberTreeNode(first).set_upper_limit(1)

    bad_sibling = _leaf_with_raw_nums(
        COSInteger.get(99),
        COSName.get_pdf_name("NotAnIntegerValue"),
    )
    _IntNumberTreeNode(bad_sibling).set_lower_limit(99)
    _IntNumberTreeNode(bad_sibling).set_upper_limit(99)

    kids = COSArray()
    kids.add(first)
    kids.add(bad_sibling)

    root_dict = COSDictionary()
    root_dict.set_item(_KIDS, kids)
    root = _IntNumberTreeNode(root_dict)

    assert root.get_value(1) == 10
    with pytest.raises(OSError, match="Expected COSInteger"):
        root.get_numbers()


def test_get_value_probes_child_when_limits_are_missing() -> None:
    child = _leaf_with_raw_nums(COSInteger.get(9), COSInteger.get(90))

    kids = COSArray()
    kids.add(child)
    root_dict = COSDictionary()
    root_dict.set_item(_KIDS, kids)
    root = _IntNumberTreeNode(root_dict)

    assert root.get_value(9) == 90
    assert root.get_value(10) is None


def test_get_value_probes_child_when_limits_are_reversed() -> None:
    child = _leaf_with_raw_nums(COSInteger.get(5), COSInteger.get(50))
    wrapped_child = _IntNumberTreeNode(child)
    wrapped_child.set_lower_limit(10)
    wrapped_child.set_upper_limit(1)

    kids = COSArray()
    kids.add(child)
    root_dict = COSDictionary()
    root_dict.set_item(_KIDS, kids)
    root = _IntNumberTreeNode(root_dict)

    assert root.get_value(5) == 50
    assert root.get_value(6) is None
