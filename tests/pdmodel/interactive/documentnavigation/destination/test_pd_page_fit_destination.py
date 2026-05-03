"""Hand-written tests for ``PDPageFitDestination`` (``/Fit`` and ``/FitB``)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitDestination,
)


def test_default_construction_writes_fit_type() -> None:
    dest = PDPageFitDestination()
    assert dest.get_type() == PDPageFitDestination.TYPE
    assert dest.get_type() == "Fit"


def test_inherits_pd_page_destination() -> None:
    dest = PDPageFitDestination()
    assert isinstance(dest, PDPageDestination)


def test_default_array_has_at_least_two_slots() -> None:
    dest = PDPageFitDestination()
    arr = dest.get_cos_array()

    assert isinstance(arr, COSArray)
    assert arr.size() >= 2
    assert arr.get_name(1) == "Fit"
    assert arr.get(0) is COSNull.NULL


def test_fit_bounding_box_default_false() -> None:
    dest = PDPageFitDestination()
    assert dest.fit_bounding_box() is False
    assert dest.is_bounded() is False


def test_set_fit_bounding_box_flips_type() -> None:
    dest = PDPageFitDestination()

    dest.set_fit_bounding_box(True)
    assert dest.get_type() == PDPageFitDestination.TYPE_BOUNDED
    assert dest.get_type() == "FitB"
    assert dest.fit_bounding_box() is True
    assert dest.is_bounded() is True

    dest.set_fit_bounding_box(False)
    assert dest.get_type() == "Fit"
    assert dest.fit_bounding_box() is False
    assert dest.is_bounded() is False


def test_constructed_from_existing_array_preserves_type() -> None:
    arr = COSArray([COSInteger.get(7), COSName.get_pdf_name("FitB")])
    dest = PDPageFitDestination(arr)

    assert dest.get_type() == "FitB"
    assert dest.fit_bounding_box() is True
    assert dest.is_bounded() is True
    assert dest.get_page_number() == 7


def test_get_cos_array_returns_underlying_array() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("Fit")])
    dest = PDPageFitDestination(arr)

    assert dest.get_cos_array() is arr
    assert dest.get_cos_object() is arr


def test_set_page_number_round_trip() -> None:
    dest = PDPageFitDestination()
    dest.set_page_number(3)

    assert dest.get_page_number() == 3
    assert dest.find_page_number() == 3
