"""Hand-written tests for ``PDPageFitHeightDestination`` (``/FitV`` / ``/FitBV``)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitHeightDestination,
)


def test_default_construction_writes_fit_v_type() -> None:
    dest = PDPageFitHeightDestination()
    assert dest.get_type() == PDPageFitHeightDestination.TYPE
    assert dest.get_type() == "FitV"


def test_inherits_pd_page_destination() -> None:
    dest = PDPageFitHeightDestination()
    assert isinstance(dest, PDPageDestination)


def test_left_default_is_none() -> None:
    dest = PDPageFitHeightDestination()
    assert dest.get_left() is None
    assert dest.is_left_unset() is True


def test_left_round_trip_set_get() -> None:
    dest = PDPageFitHeightDestination()

    dest.set_left(36.5)
    assert dest.get_left() == 36.5
    assert dest.is_left_unset() is False

    dest.set_left(None)
    assert dest.get_left() is None
    assert dest.is_left_unset() is True


def test_left_accepts_int_value_returns_float() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSName.get_pdf_name("FitV"), COSInteger.get(50)]
    )
    dest = PDPageFitHeightDestination(arr)

    assert dest.get_left() == 50.0
    assert dest.is_left_unset() is False


def test_left_round_trip_via_existing_cos_float() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSName.get_pdf_name("FitV"), COSFloat(123.25)]
    )
    dest = PDPageFitHeightDestination(arr)

    assert dest.get_left() == 123.25


def test_clear_left_writes_cos_null() -> None:
    dest = PDPageFitHeightDestination()
    dest.set_left(72.0)
    assert dest.get_left() == 72.0

    dest.clear_left()
    assert dest.get_left() is None
    assert dest.is_left_unset() is True
    assert dest.get_cos_array().get(2) is COSNull.NULL


def test_clear_left_grows_array_when_short() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("FitV")])
    dest = PDPageFitHeightDestination(arr)

    dest.clear_left()
    assert dest.get_cos_array().size() >= 3
    assert dest.get_cos_array().get(2) is COSNull.NULL


def test_fit_bounding_box_default_false() -> None:
    dest = PDPageFitHeightDestination()
    assert dest.fit_bounding_box() is False
    assert dest.is_bounded() is False


def test_set_fit_bounding_box_flips_type() -> None:
    dest = PDPageFitHeightDestination()

    dest.set_fit_bounding_box(True)
    assert dest.get_type() == PDPageFitHeightDestination.TYPE_BOUNDED
    assert dest.get_type() == "FitBV"
    assert dest.is_bounded() is True

    dest.set_fit_bounding_box(False)
    assert dest.get_type() == "FitV"
    assert dest.is_bounded() is False


def test_set_page_number_round_trip() -> None:
    dest = PDPageFitHeightDestination()
    dest.set_page_number(2)
    assert dest.get_page_number() == 2
