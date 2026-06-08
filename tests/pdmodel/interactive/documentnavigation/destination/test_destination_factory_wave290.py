from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDDestinationNameTreeNode,
    PDPageFitDestination,
    PDPageFitHeightDestination,
    PDPageFitWidthDestination,
)


def _destination_array(type_name: str) -> COSArray:
    return COSArray([COSInteger.get(0), COSName.get_pdf_name(type_name)])


def test_create_fit_bounding_box_reuses_fit_destination() -> None:
    destination = PDDestination.create(_destination_array("FitB"))

    assert isinstance(destination, PDPageFitDestination)
    assert destination.get_type() == "FitB"


def test_create_fit_bounding_box_width_reuses_fit_width_destination() -> None:
    destination = PDDestination.create(_destination_array("FitBH"))

    assert isinstance(destination, PDPageFitWidthDestination)
    assert destination.get_type() == "FitBH"


def test_create_fit_bounding_box_height_reuses_fit_height_destination() -> None:
    destination = PDDestination.create(_destination_array("FitBV"))

    assert isinstance(destination, PDPageFitHeightDestination)
    assert destination.get_type() == "FitBV"


def test_name_tree_resolves_fit_bounding_box_leaf_to_fit_wrapper() -> None:
    names = COSArray()
    names.add(COSString("bounded"))
    names.add(_destination_array("FitB"))
    node = COSDictionary()
    node.set_item(COSName.get_pdf_name("Names"), names)

    destination = PDDestinationNameTreeNode(node).get_value("bounded")

    assert isinstance(destination, PDPageFitDestination)
    assert destination.get_page_number() == 0
