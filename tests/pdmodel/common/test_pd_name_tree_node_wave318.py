from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NAMES = COSName.get_pdf_name("Names")
_LIMITS = COSName.get_pdf_name("Limits")


def _raw_leaf(name: str, value: str, *, with_limits: bool) -> COSDictionary:
    leaf = COSDictionary()
    names = COSArray()
    names.add(COSString(name))
    names.add(COSString(value))
    leaf.set_item(_NAMES, names)
    if with_limits:
        limits = COSArray()
        limits.add(COSString(name))
        limits.add(COSString(name))
        leaf.set_item(_LIMITS, limits)
    return leaf


def test_wave318_get_value_continues_after_limitless_child_miss() -> None:
    first = _raw_leaf("alpha", "A", with_limits=False)
    second = _raw_leaf("bravo", "B", with_limits=True)
    kids = COSArray()
    kids.add(first)
    kids.add(second)
    root_dict = COSDictionary()
    root_dict.set_item(_KIDS, kids)

    root = PDStringNameTreeNode(root_dict)

    assert root.get_value("bravo") == "B"


def test_get_value_continues_after_stale_limit_match_miss() -> None:
    stale = _raw_leaf("alpha", "A", with_limits=True)
    limits = stale.get_dictionary_object(_LIMITS)
    assert isinstance(limits, COSArray)
    limits.set(1, COSString("charlie"))

    target = _raw_leaf("bravo", "B", with_limits=True)
    kids = COSArray()
    kids.add(stale)
    kids.add(target)
    root_dict = COSDictionary()
    root_dict.set_item(_KIDS, kids)

    root = PDStringNameTreeNode(root_dict)

    assert root.get_value("bravo") == "B"
