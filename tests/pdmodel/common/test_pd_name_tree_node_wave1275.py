"""Wave 1275 parity test for PDNameTreeNode.calculate_limits public alias."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSString
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode


def test_calculate_limits_public_alias_recomputes_limits() -> None:
    # Build a leaf-shape node with two names; intermediate parent so /Limits
    # is actually computed (root nodes drop /Limits per spec).
    leaf_dict = COSDictionary()
    names_arr = COSArray()
    for k, v in [("alpha", "1"), ("zeta", "2")]:
        names_arr.add(COSString(k))
        names_arr.add(COSString(v))
    leaf_dict.set_item("Names", names_arr)
    leaf = PDStringNameTreeNode(leaf_dict)

    parent_dict = COSDictionary()
    parent = PDStringNameTreeNode(parent_dict)
    leaf.set_parent(parent)

    # Tamper with /Limits and recompute via the public alias.
    leaf.set_lower_limit("aaa")
    leaf.set_upper_limit("zzz")
    leaf.calculate_limits()
    assert leaf.get_lower_limit() == "alpha"
    assert leaf.get_upper_limit() == "zeta"
