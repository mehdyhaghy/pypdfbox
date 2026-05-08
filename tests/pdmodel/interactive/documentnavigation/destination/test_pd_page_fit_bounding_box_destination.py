"""Hand-written tests for ``PDPageFitBoundingBoxDestination`` (``/FitB``)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitBoundingBoxDestination,
)


def test_default_construction_writes_fit_b_type() -> None:
    dest = PDPageFitBoundingBoxDestination()
    assert dest.get_type() == PDPageFitBoundingBoxDestination.TYPE
    assert dest.get_type() == "FitB"


def test_inherits_pd_page_destination() -> None:
    dest = PDPageFitBoundingBoxDestination()
    assert isinstance(dest, PDPageDestination)


def test_get_cos_array_returns_underlying_array() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("FitB")])
    dest = PDPageFitBoundingBoxDestination(arr)

    assert dest.get_cos_array() is arr
    assert dest.get_cos_object() is arr


def test_default_array_has_at_least_two_slots() -> None:
    dest = PDPageFitBoundingBoxDestination()
    arr = dest.get_cos_array()

    assert isinstance(arr, COSArray)
    assert arr.size() >= 2
    assert arr.get_name(1) == "FitB"
    assert arr.get(0) is COSNull.NULL


def test_set_and_get_page_number_round_trip() -> None:
    dest = PDPageFitBoundingBoxDestination()
    dest.set_page_number(4)

    assert dest.get_page_number() == 4
    assert dest.find_page_number() == 4


def test_constructed_from_existing_array_preserves_type() -> None:
    arr = COSArray([COSInteger.get(7), COSName.get_pdf_name("FitB")])
    dest = PDPageFitBoundingBoxDestination(arr)

    assert dest.get_type() == "FitB"
    assert dest.get_page_number() == 7
