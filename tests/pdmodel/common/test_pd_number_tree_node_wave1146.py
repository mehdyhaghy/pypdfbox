from __future__ import annotations

from pypdfbox.cos import COSInteger
from tests.pdmodel.common.test_pd_number_tree_node_wave297 import _IntNumberTreeNode


def test_wave1146_int_number_tree_node_converts_value_to_cos_integer() -> None:
    converted = _IntNumberTreeNode().convert_value_to_cos(1150)

    assert isinstance(converted, COSInteger)
    assert converted.value == 1150
