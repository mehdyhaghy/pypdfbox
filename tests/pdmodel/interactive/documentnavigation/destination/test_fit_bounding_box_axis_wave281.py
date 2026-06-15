from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSNull, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitHeightDestination,
    PDPageFitWidthDestination,
)

# The /FitBH (bounding-box width) and /FitBV (bounding-box height) variants are
# carried by the real PDPageFitWidthDestination / PDPageFitHeightDestination
# classes via their TYPE_BOUNDED flag — PDFBox has no dedicated bounding-box
# subclass. These tests exercise the axis-specific top/left slot behaviour for
# the bounded variant.


def test_fit_bounding_box_width_top_unset_predicate_and_clear() -> None:
    dest = PDPageFitWidthDestination()
    dest.set_fit_bounding_box(True)

    assert dest.is_top_unset() is True

    dest.set_top(240.0)
    assert dest.is_top_unset() is False

    dest.clear_top()
    assert dest.get_top() is None
    assert dest.is_top_unset() is True
    assert dest.get_cos_array().get(2) is COSNull.NULL


def test_fit_bounding_box_width_top_unset_for_malformed_value() -> None:
    arr = COSArray(
        [
            COSInteger.get(0),
            COSName.get_pdf_name("FitBH"),
            COSString("not numeric"),
        ]
    )
    dest = PDPageFitWidthDestination(arr)

    assert dest.get_top() is None
    assert dest.is_top_unset() is True


def test_fit_bounding_box_width_clear_grows_short_array() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("FitBH")])
    dest = PDPageFitWidthDestination(arr)

    dest.clear_top()

    assert arr.size() == 3
    assert arr.get(2) is COSNull.NULL


def test_fit_bounding_box_height_left_unset_predicate_and_clear() -> None:
    dest = PDPageFitHeightDestination()
    dest.set_fit_bounding_box(True)

    assert dest.is_left_unset() is True

    dest.set_left(128.0)
    assert dest.is_left_unset() is False

    dest.clear_left()
    assert dest.get_left() is None
    assert dest.is_left_unset() is True
    assert dest.get_cos_array().get(2) is COSNull.NULL


def test_fit_bounding_box_height_left_unset_for_malformed_value() -> None:
    arr = COSArray(
        [
            COSInteger.get(0),
            COSName.get_pdf_name("FitBV"),
            COSString("not numeric"),
        ]
    )
    dest = PDPageFitHeightDestination(arr)

    assert dest.get_left() is None
    assert dest.is_left_unset() is True


def test_fit_bounding_box_height_clear_grows_short_array() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("FitBV")])
    dest = PDPageFitHeightDestination(arr)

    dest.clear_left()

    assert arr.size() == 3
    assert arr.get(2) is COSNull.NULL
