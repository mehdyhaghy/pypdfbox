from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger
from pypdfbox.pdmodel import PDPageTree
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    _remove_array_kid,
    _same_kid,
)


def test_wave822_remove_array_kid_falls_back_to_raw_int_equivalence() -> None:
    raw_kids = COSArray()
    raw_kids.add(1234)  # type: ignore[arg-type]
    raw_kids.add(COSInteger.get(9))

    assert _remove_array_kid(raw_kids, COSInteger.get(1234)) is True

    assert raw_kids.size() == 1
    assert raw_kids.get_object(0) == COSInteger.get(9)


def test_wave822_same_kid_matches_plain_int_and_cos_integer_both_orders() -> None:
    assert _same_kid(COSInteger.get(42), 42) is True
    assert _same_kid(42, COSInteger.get(42)) is True


def test_wave822_page_tree_getitem_rejects_non_integer_index() -> None:
    tree = PDPageTree()

    with pytest.raises(TypeError, match="indices must be int"):
        tree[object()]  # type: ignore[index]
