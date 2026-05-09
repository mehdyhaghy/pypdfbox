from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    PDStructureNode,
    _same_kid,
)

_K = COSName.get_pdf_name("K")


def test_wave801_remove_kid_falls_back_to_raw_integer_match() -> None:
    node = PDStructureNode("StructElem")
    raw_kids = COSArray()
    raw_kids.add(COSInteger.get(1))
    raw_kids.add(9000)  # type: ignore[arg-type]
    node.get_cos_object().set_item(_K, raw_kids)

    assert node.remove_kid(9000) is True

    remaining = node.get_cos_object().get_dictionary_object(_K)
    assert remaining == COSInteger.get(1)


def test_wave801_same_kid_matches_cos_integer_to_plain_int() -> None:
    assert _same_kid(COSInteger.get(42), 42) is True
