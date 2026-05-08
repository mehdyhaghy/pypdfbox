from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestinationNameTreeNode,
)

_NAMES: COSName = COSName.get_pdf_name("Names")


def _tree_with_destination(value: COSArray) -> PDDestinationNameTreeNode:
    names = COSArray()
    names.add(COSString("bad"))
    names.add(value)

    node = COSDictionary()
    node.set_item(_NAMES, names)
    return PDDestinationNameTreeNode(node)


def test_malformed_short_destination_array_returns_none() -> None:
    tree = _tree_with_destination(COSArray([COSInteger.get(0)]))

    assert tree.get_value("bad") is None


def test_destination_array_with_non_name_type_returns_none() -> None:
    tree = _tree_with_destination(COSArray([COSInteger.get(0), COSInteger.get(1)]))

    assert tree.get_value("bad") is None


def test_destination_array_with_unknown_type_returns_none() -> None:
    tree = _tree_with_destination(
        COSArray([COSInteger.get(0), COSName.get_pdf_name("NotADestination")])
    )

    assert tree.get_value("bad") is None
