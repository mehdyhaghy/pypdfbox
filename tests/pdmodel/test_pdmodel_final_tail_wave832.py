from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger
from pypdfbox.pdmodel import PDDeveloperExtension, PDPageTree
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    _remove_array_kid,
    _same_kid,
)
from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
    PDDocumentNameDestinationDictionary,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary


def test_wave832_structure_array_removal_falls_back_to_integer_equivalence() -> None:
    kids = COSArray()
    kids.add(COSInteger.get(7))
    kids.add(99)  # type: ignore[arg-type]

    assert _remove_array_kid(kids, COSInteger.get(99)) is True

    assert kids.size() == 1
    assert kids.get_object(0) == COSInteger.get(7)


def test_wave832_same_kid_matches_plain_and_cos_integer_both_orders() -> None:
    assert _same_kid(COSInteger.get(5), 5) is True
    assert _same_kid(5, COSInteger.get(5)) is True
    assert _same_kid(COSInteger.get(5), 6) is False


def test_wave832_page_tree_getitem_rejects_non_integer_index() -> None:
    tree = PDPageTree()

    with pytest.raises(TypeError, match="indices must be int"):
        tree[object()]  # type: ignore[index]


def test_wave832_dictionary_wrappers_return_raw_cos_dictionary_alias() -> None:
    names = COSDictionary()
    destination_names = COSDictionary()
    developer_extension = COSDictionary()

    name_dictionary = PDDocumentNameDictionary(names=names)
    destination_dictionary = PDDocumentNameDestinationDictionary(destination_names)
    extension = PDDeveloperExtension(developer_extension)

    assert name_dictionary.get_cos_dictionary() is names
    assert destination_dictionary.get_cos_dictionary() is destination_names
    assert extension.get_cos_dictionary() is developer_extension
