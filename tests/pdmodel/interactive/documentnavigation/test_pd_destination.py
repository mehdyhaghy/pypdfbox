from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDNamedDestination,
    PDPageFitDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)


def test_named_destination_from_name_and_string() -> None:
    by_name = PDDestination.create(COSName.get_pdf_name("Chapter1"))
    by_string = PDDestination.create(COSString("Chapter2"))

    assert isinstance(by_name, PDNamedDestination)
    assert by_name.get_named_destination() == "Chapter1"
    assert isinstance(by_string, PDNamedDestination)
    assert by_string.get_named_destination() == "Chapter2"


def test_page_fit_destination_defaults_and_bounding_box_flag() -> None:
    dest = PDPageFitDestination()
    dest.set_page_number(2)
    assert dest.get_type() == "Fit"
    assert dest.get_page_number() == 2
    assert not dest.fit_bounding_box()

    dest.set_fit_bounding_box(True)
    assert dest.get_type() == "FitB"
    assert dest.fit_bounding_box()


def test_page_width_height_and_xyz_coordinates() -> None:
    width = PDPageFitWidthDestination()
    width.set_top(700)
    assert width.get_top() == 700.0
    width.set_fit_bounding_box(True)
    assert width.get_type() == "FitBH"

    height = PDPageFitHeightDestination()
    height.set_left(12.5)
    assert height.get_left() == 12.5
    height.set_fit_bounding_box(True)
    assert height.get_type() == "FitBV"

    xyz = PDPageXYZDestination()
    xyz.set_left(10)
    xyz.set_top(20)
    xyz.set_zoom(1.25)
    assert xyz.get_left() == 10.0
    assert xyz.get_top() == 20.0
    assert xyz.get_zoom() == 1.25

    rectangle = PDPageFitRectangleDestination()
    rectangle.set_left(1)
    rectangle.set_bottom(2)
    rectangle.set_right(3)
    rectangle.set_top(4)
    assert rectangle.get_left() == 1.0
    assert rectangle.get_bottom() == 2.0
    assert rectangle.get_right() == 3.0
    assert rectangle.get_top() == 4.0


def test_destination_factory_dispatches_array_types() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ"), COSFloat(1.0)])
    assert isinstance(PDDestination.create(arr), PDPageXYZDestination)

    arr.set(1, COSName.get_pdf_name("FitH"))
    assert isinstance(PDDestination.create(arr), PDPageFitWidthDestination)

    arr.set(1, COSName.get_pdf_name("FitV"))
    assert isinstance(PDDestination.create(arr), PDPageFitHeightDestination)

    arr.set(1, COSName.get_pdf_name("Fit"))
    assert isinstance(PDDestination.create(arr), PDPageFitDestination)

    arr.set(1, COSName.get_pdf_name("FitR"))
    assert isinstance(PDDestination.create(arr), PDPageFitRectangleDestination)


def test_destination_factory_rejects_unknown_array_type() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("UnknownDest")])
    with pytest.raises(OSError):
        PDDestination.create(arr)
