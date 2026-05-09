from __future__ import annotations

import logging

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_LIMITS = COSName.get_pdf_name("Limits")
_NAMES = COSName.get_pdf_name("Names")


def test_set_names_builds_intermediate_level_for_more_than_sixty_four_leaves() -> None:
    tree = PDStringNameTreeNode()
    names = {f"k{i:04d}": f"v{i:04d}" for i in range(4097)}

    tree.set_names(names)

    root_kids = tree.get_cos_object().get_dictionary_object(_KIDS)
    assert isinstance(root_kids, COSArray)
    assert root_kids.size() == 2

    first_intermediate = root_kids.get_object(0)
    second_intermediate = root_kids.get_object(1)
    assert isinstance(first_intermediate, COSDictionary)
    assert isinstance(second_intermediate, COSDictionary)

    first_intermediate_kids = first_intermediate.get_dictionary_object(_KIDS)
    second_intermediate_kids = second_intermediate.get_dictionary_object(_KIDS)
    assert isinstance(first_intermediate_kids, COSArray)
    assert isinstance(second_intermediate_kids, COSArray)
    assert first_intermediate_kids.size() == 64
    assert second_intermediate_kids.size() == 1

    first_node = PDStringNameTreeNode(first_intermediate)
    second_node = PDStringNameTreeNode(second_intermediate)
    assert first_node.get_lower_limit() == "k0000"
    assert first_node.get_upper_limit() == "k4095"
    assert second_node.get_lower_limit() == "k4096"
    assert second_node.get_upper_limit() == "k4096"
    assert tree.get_value("k4096") == "v4096"
    assert tree.get_number_of_values() == 4097


def test_limit_recalculation_clears_limits_when_names_array_is_malformed(
    caplog,
) -> None:
    malformed_names = COSArray()
    malformed_names.add(COSName.get_pdf_name("NotAString"))
    malformed_names.add(COSString("value"))

    child_dict = COSDictionary()
    child_dict.set_item(_NAMES, malformed_names)
    limits = COSArray()
    limits.add(COSString("old-low"))
    limits.add(COSString("old-high"))
    child_dict.set_item(_LIMITS, limits)

    child = PDStringNameTreeNode(child_dict)

    with caplog.at_level(logging.ERROR, "pypdfbox.pdmodel.common.pd_name_tree_node"):
        child.set_parent(PDStringNameTreeNode())

    assert child.get_cos_object().get_dictionary_object(_LIMITS) is None
    assert "Error while calculating the Limits of a name tree node" in caplog.text
