from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitRectangleDestination,
    PDPageXYZDestination,
)


def test_xyz_left_setter_grows_short_array_to_full_destination_shape() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)

    dest.set_left(72.5)

    assert arr.size() == 5
    assert arr.get(2) == COSFloat(72.5)
    assert arr.get(3) is COSNull.NULL
    assert arr.get(4) is COSNull.NULL


def test_fit_rectangle_left_setter_grows_short_array_to_full_destination_shape() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("FitR")])
    dest = PDPageFitRectangleDestination(arr)

    dest.set_left(10.0)

    assert arr.size() == 6
    assert arr.get(2) == COSFloat(10.0)
    assert arr.get(3) is COSNull.NULL
    assert arr.get(4) is COSNull.NULL
    assert arr.get(5) is COSNull.NULL
