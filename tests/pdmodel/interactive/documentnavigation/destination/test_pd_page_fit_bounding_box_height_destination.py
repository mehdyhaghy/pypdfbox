"""Hand-written tests for ``PDPageFitBoundingBoxHeightDestination`` (``/FitBV``)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitBoundingBoxHeightDestination,
)


def test_default_construction_writes_fit_bv_type() -> None:
    dest = PDPageFitBoundingBoxHeightDestination()
    assert dest.get_type() == PDPageFitBoundingBoxHeightDestination.TYPE
    assert dest.get_type() == "FitBV"


def test_inherits_pd_page_destination() -> None:
    dest = PDPageFitBoundingBoxHeightDestination()
    assert isinstance(dest, PDPageDestination)


def test_left_default_is_none() -> None:
    dest = PDPageFitBoundingBoxHeightDestination()
    assert dest.get_left() is None


def test_left_round_trip_set_get() -> None:
    dest = PDPageFitBoundingBoxHeightDestination()

    dest.set_left(72.5)
    assert dest.get_left() == 72.5

    dest.set_left(None)
    assert dest.get_left() is None


def test_left_accepts_int_value_returns_float() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSName.get_pdf_name("FitBV"), COSInteger.get(50)]
    )
    dest = PDPageFitBoundingBoxHeightDestination(arr)

    assert dest.get_left() == 50.0


def test_left_round_trip_via_existing_cos_float() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSName.get_pdf_name("FitBV"), COSFloat(123.25)]
    )
    dest = PDPageFitBoundingBoxHeightDestination(arr)

    assert dest.get_left() == 123.25


def test_set_page_number_round_trip() -> None:
    dest = PDPageFitBoundingBoxHeightDestination()
    dest.set_page_number(2)
    assert dest.get_page_number() == 2
