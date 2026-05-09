from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestinationNameTreeNode,
    PDPageDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)


def _item(title: str) -> PDOutlineItem:
    item = PDOutlineItem()
    item.set_title(title)
    return item


def test_page_destination_rejects_uncoercible_page_and_unknown_context() -> None:
    dest = PDPageDestination()

    with pytest.raises(TypeError, match="Cannot set page"):
        dest.set_page(object())

    dest.set_page(COSDictionary())

    assert dest.find_page_number(object()) == -1


def test_destination_name_tree_none_value_and_empty_names_alias() -> None:
    tree = PDDestinationNameTreeNode()

    assert tree.convert_value_to_cos(None) is COSNull.NULL
    assert tree.names() == []


def test_outline_insert_before_middle_relinks_previous_neighbor() -> None:
    parent = PDDocumentOutline()
    first = _item("first")
    third = _item("third")
    parent.add_last(first)
    parent.add_last(third)
    second = _item("second")

    third.insert_sibling_before(second)

    assert parent.get_first_child().get_cos_object() is first.get_cos_object()
    assert parent.get_last_child().get_cos_object() is third.get_cos_object()
    assert first.get_next_sibling().get_cos_object() is second.get_cos_object()
    assert second.get_previous_sibling().get_cos_object() is first.get_cos_object()
    assert second.get_next_sibling().get_cos_object() is third.get_cos_object()
    assert third.get_previous_sibling().get_cos_object() is second.get_cos_object()


def test_outline_text_color_returns_none_when_component_is_non_numeric() -> None:
    item = PDOutlineItem()
    color = COSArray()
    color.add(COSFloat(1.0))
    color.add(COSName.get_pdf_name("NotANumber"))
    color.add(COSFloat(0.0))
    item.get_cos_object().set_item(COSName.C, color)

    assert item.get_text_color() is None
