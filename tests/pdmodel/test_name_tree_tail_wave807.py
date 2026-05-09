from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSString
from pypdfbox.pdmodel.pd_alternate_presentations_name_tree_node import (
    PDAlternatePresentationsNameTreeNode,
)
from pypdfbox.pdmodel.pd_ids_name_tree_node import PDIDSNameTreeNode
from pypdfbox.pdmodel.pd_pages_name_tree_node import PDPagesNameTreeNode
from pypdfbox.pdmodel.pd_renditions_name_tree_node import PDRenditionsNameTreeNode
from pypdfbox.pdmodel.pd_templates_name_tree_node import PDTemplatesNameTreeNode
from pypdfbox.pdmodel.pd_urls_name_tree_node import PDURLSNameTreeNode


@pytest.mark.parametrize(
    ("tree_cls", "name"),
    [
        (PDAlternatePresentationsNameTreeNode, "AlternatePresentations"),
        (PDPagesNameTreeNode, "Pages"),
        (PDRenditionsNameTreeNode, "Renditions"),
        (PDTemplatesNameTreeNode, "Templates"),
        (PDURLSNameTreeNode, "URLS"),
    ],
)
def test_dictionary_leaf_name_trees_reject_non_dictionary_values(
    tree_cls: type[
        PDAlternatePresentationsNameTreeNode
        | PDPagesNameTreeNode
        | PDRenditionsNameTreeNode
        | PDTemplatesNameTreeNode
        | PDURLSNameTreeNode
    ],
    name: str,
) -> None:
    tree = tree_cls()

    with pytest.raises(OSError, match=rf"Expected dictionary for /{name}"):
        tree.convert_cos_to_value(COSString("not a dictionary"))


def test_ids_name_tree_rejects_non_string_leaf_values() -> None:
    tree = PDIDSNameTreeNode()

    with pytest.raises(OSError, match=r"Expected string for /IDS"):
        tree.convert_cos_to_value(COSDictionary())
