from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSNull
from tests.pdmodel.common import test_pd_stream_number_tree_wave727 as wave727


def test_wave895_nullable_number_tree_converts_null_and_integers() -> None:
    tree = wave727._NullableNumberTreeNode()  # noqa: SLF001

    assert tree.convert_cos_to_value(COSNull.NULL) is None
    assert tree.convert_cos_to_value(COSInteger.get(42)) == 42
    assert tree.convert_value_to_cos(None) is COSNull.NULL
    assert tree.convert_value_to_cos(7) is COSInteger.get(7)


def test_wave895_nullable_number_tree_rejects_non_integer_values() -> None:
    tree = wave727._NullableNumberTreeNode()  # noqa: SLF001

    with pytest.raises(OSError, match="Expected COSInteger"):
        tree.convert_cos_to_value(COSName.get_pdf_name("Nope"))


def test_wave895_nullable_number_tree_child_node_preserves_dictionary() -> None:
    root = wave727._NullableNumberTreeNode()  # noqa: SLF001
    child_dict = COSDictionary()

    child = root.create_child_node(child_dict)

    assert isinstance(child, wave727._NullableNumberTreeNode)  # noqa: SLF001
    assert child.get_cos_object() is child_dict
