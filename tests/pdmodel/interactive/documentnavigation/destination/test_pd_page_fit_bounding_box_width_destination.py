"""Hand-written tests for ``PDPageFitBoundingBoxWidthDestination`` (``/FitBH``)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitBoundingBoxWidthDestination,
)


def test_default_construction_writes_fit_bh_type() -> None:
    dest = PDPageFitBoundingBoxWidthDestination()
    assert dest.get_type() == PDPageFitBoundingBoxWidthDestination.TYPE
    assert dest.get_type() == "FitBH"


def test_inherits_pd_page_destination() -> None:
    dest = PDPageFitBoundingBoxWidthDestination()
    assert isinstance(dest, PDPageDestination)


def test_top_default_is_none() -> None:
    dest = PDPageFitBoundingBoxWidthDestination()
    assert dest.get_top() is None


def test_top_round_trip_set_get() -> None:
    dest = PDPageFitBoundingBoxWidthDestination()

    dest.set_top(540.0)
    assert dest.get_top() == 540.0

    dest.set_top(None)
    assert dest.get_top() is None


def test_top_accepts_int_value_returns_float() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSName.get_pdf_name("FitBH"), COSInteger.get(700)]
    )
    dest = PDPageFitBoundingBoxWidthDestination(arr)

    assert dest.get_top() == 700.0


def test_top_round_trip_via_existing_cos_float() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSName.get_pdf_name("FitBH"), COSFloat(456.75)]
    )
    dest = PDPageFitBoundingBoxWidthDestination(arr)

    assert dest.get_top() == 456.75


def test_set_page_number_round_trip() -> None:
    dest = PDPageFitBoundingBoxWidthDestination()
    dest.set_page_number(8)
    assert dest.get_page_number() == 8
