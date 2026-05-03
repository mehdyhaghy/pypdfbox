"""Hand-written tests for ``PDPageFitWidthDestination`` (``/FitH`` / ``/FitBH``)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitWidthDestination,
)


def test_default_construction_writes_fit_h_type() -> None:
    dest = PDPageFitWidthDestination()
    assert dest.get_type() == PDPageFitWidthDestination.TYPE
    assert dest.get_type() == "FitH"


def test_inherits_pd_page_destination() -> None:
    dest = PDPageFitWidthDestination()
    assert isinstance(dest, PDPageDestination)


def test_top_default_is_none() -> None:
    dest = PDPageFitWidthDestination()
    assert dest.get_top() is None
    assert dest.is_top_unset() is True


def test_top_round_trip_set_get() -> None:
    dest = PDPageFitWidthDestination()

    dest.set_top(720.5)
    assert dest.get_top() == 720.5
    assert dest.is_top_unset() is False

    dest.set_top(None)
    assert dest.get_top() is None
    assert dest.is_top_unset() is True


def test_top_accepts_int_value_returns_float() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSName.get_pdf_name("FitH"), COSInteger.get(100)]
    )
    dest = PDPageFitWidthDestination(arr)

    assert dest.get_top() == 100.0
    assert dest.is_top_unset() is False


def test_top_round_trip_via_existing_cos_float() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSName.get_pdf_name("FitH"), COSFloat(842.25)]
    )
    dest = PDPageFitWidthDestination(arr)

    assert dest.get_top() == 842.25


def test_clear_top_writes_cos_null() -> None:
    dest = PDPageFitWidthDestination()
    dest.set_top(123.0)
    assert dest.get_top() == 123.0

    dest.clear_top()
    assert dest.get_top() is None
    assert dest.is_top_unset() is True
    assert dest.get_cos_array().get(2) is COSNull.NULL


def test_clear_top_grows_array_when_short() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("FitH")])
    dest = PDPageFitWidthDestination(arr)

    dest.clear_top()
    assert dest.get_cos_array().size() >= 3
    assert dest.get_cos_array().get(2) is COSNull.NULL


def test_fit_bounding_box_default_false() -> None:
    dest = PDPageFitWidthDestination()
    assert dest.fit_bounding_box() is False
    assert dest.is_bounded() is False


def test_set_fit_bounding_box_flips_type() -> None:
    dest = PDPageFitWidthDestination()

    dest.set_fit_bounding_box(True)
    assert dest.get_type() == PDPageFitWidthDestination.TYPE_BOUNDED
    assert dest.get_type() == "FitBH"
    assert dest.fit_bounding_box() is True
    assert dest.is_bounded() is True

    dest.set_fit_bounding_box(False)
    assert dest.get_type() == "FitH"
    assert dest.is_bounded() is False


def test_set_page_number_round_trip() -> None:
    dest = PDPageFitWidthDestination()
    dest.set_page_number(1)
    assert dest.get_page_number() == 1
