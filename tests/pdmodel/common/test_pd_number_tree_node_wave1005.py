from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from tests.pdmodel.common.test_pd_number_tree_node_wave273 import _IntNumberTreeNode


def test_int_number_tree_node_rejects_non_integer_cos_value() -> None:
    tree = _IntNumberTreeNode()

    with pytest.raises(OSError, match="Expected COSInteger, got COSName"):
        tree.convert_cos_to_value(COSName.TYPE)  # type: ignore[attr-defined]


def test_int_number_tree_node_create_child_wraps_dictionary() -> None:
    tree = _IntNumberTreeNode()
    dictionary = COSDictionary()

    child = tree.create_child_node(dictionary)

    assert isinstance(child, _IntNumberTreeNode)
    assert child.get_cos_object() is dictionary
