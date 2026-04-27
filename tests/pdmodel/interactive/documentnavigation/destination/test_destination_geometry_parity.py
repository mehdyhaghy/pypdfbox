"""Parity tests for geometry accessors on ``PDPageDestination`` subclasses.

Covers default values when the underlying ``/D`` array slots are absent and
round-trip set/get behavior. Mirrors the parameter layout from PDF 32000-1
Table 151:

* XYZ:  ``[page /XYZ left top zoom]``
* FitH: ``[page /FitH top]`` (and ``/FitBH`` bounded variant)
* FitV: ``[page /FitV left]`` (and ``/FitBV`` bounded variant)
* FitR: ``[page /FitR left bottom right top]``
"""

from __future__ import annotations

from pypdfbox.cos import COSArray
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)


# ---------------------------------------------------------------------------
# PDPageXYZDestination
# ---------------------------------------------------------------------------


def test_xyz_defaults_are_none() -> None:
    dest = PDPageXYZDestination()

    assert dest.get_left() is None
    assert dest.get_top() is None
    assert dest.get_zoom() is None


def test_xyz_round_trip_left_top_zoom() -> None:
    dest = PDPageXYZDestination()

    dest.set_left(72.5)
    dest.set_top(540.25)
    dest.set_zoom(1.5)

    assert dest.get_left() == 72.5
    assert dest.get_top() == 540.25
    assert dest.get_zoom() == 1.5


def test_xyz_clearing_fields_round_trips_to_none() -> None:
    dest = PDPageXYZDestination()
    dest.set_left(10.0)
    dest.set_top(20.0)
    dest.set_zoom(0.0)

    dest.set_left(None)
    dest.set_top(None)
    dest.set_zoom(None)

    assert dest.get_left() is None
    assert dest.get_top() is None
    assert dest.get_zoom() is None


def test_xyz_zoom_zero_is_returned_verbatim() -> None:
    """Per PDF 32000-1: ``zoom == 0`` means 'leave unchanged'. We must not
    coerce it to ``None`` on read."""
    dest = PDPageXYZDestination()
    dest.set_zoom(0.0)

    assert dest.get_zoom() == 0.0


def test_xyz_partial_array_returns_none_for_missing_slots() -> None:
    arr = COSArray()
    dest = PDPageXYZDestination(arr)
    dest._set_type(PDPageXYZDestination.TYPE)

    assert dest.get_left() is None
    assert dest.get_top() is None
    assert dest.get_zoom() is None


# ---------------------------------------------------------------------------
# PDPageFitHeightDestination  (TYPE = "FitV", parameter = left)
# ---------------------------------------------------------------------------


def test_fit_height_defaults_are_none() -> None:
    dest = PDPageFitHeightDestination()

    assert dest.get_left() is None
    assert dest.fit_bounding_box() is False


def test_fit_height_round_trip_left() -> None:
    dest = PDPageFitHeightDestination()

    dest.set_left(123.5)
    assert dest.get_left() == 123.5

    dest.set_left(None)
    assert dest.get_left() is None


def test_fit_height_bounded_variant_toggle() -> None:
    dest = PDPageFitHeightDestination()
    assert dest.get_type() == "FitV"

    dest.set_fit_bounding_box(True)
    assert dest.fit_bounding_box() is True
    assert dest.get_type() == "FitBV"

    dest.set_fit_bounding_box(False)
    assert dest.fit_bounding_box() is False
    assert dest.get_type() == "FitV"


# ---------------------------------------------------------------------------
# PDPageFitWidthDestination  (TYPE = "FitH", parameter = top)
# ---------------------------------------------------------------------------


def test_fit_width_defaults_are_none() -> None:
    dest = PDPageFitWidthDestination()

    assert dest.get_top() is None
    assert dest.fit_bounding_box() is False


def test_fit_width_round_trip_top() -> None:
    dest = PDPageFitWidthDestination()

    dest.set_top(456.75)
    assert dest.get_top() == 456.75

    dest.set_top(None)
    assert dest.get_top() is None


def test_fit_width_bounded_variant_toggle() -> None:
    dest = PDPageFitWidthDestination()
    assert dest.get_type() == "FitH"

    dest.set_fit_bounding_box(True)
    assert dest.fit_bounding_box() is True
    assert dest.get_type() == "FitBH"

    dest.set_fit_bounding_box(False)
    assert dest.fit_bounding_box() is False
    assert dest.get_type() == "FitH"


# ---------------------------------------------------------------------------
# PDPageFitRectangleDestination  (TYPE = "FitR", params = left/bottom/right/top)
# ---------------------------------------------------------------------------


def test_fit_rectangle_defaults_are_none() -> None:
    dest = PDPageFitRectangleDestination()

    assert dest.get_left() is None
    assert dest.get_bottom() is None
    assert dest.get_right() is None
    assert dest.get_top() is None


def test_fit_rectangle_round_trip_all_corners() -> None:
    dest = PDPageFitRectangleDestination()

    dest.set_left(10.0)
    dest.set_bottom(20.0)
    dest.set_right(110.0)
    dest.set_top(220.0)

    assert dest.get_left() == 10.0
    assert dest.get_bottom() == 20.0
    assert dest.get_right() == 110.0
    assert dest.get_top() == 220.0


def test_fit_rectangle_clear_individual_corners() -> None:
    dest = PDPageFitRectangleDestination()
    dest.set_left(1.0)
    dest.set_bottom(2.0)
    dest.set_right(3.0)
    dest.set_top(4.0)

    dest.set_bottom(None)
    dest.set_right(None)

    assert dest.get_left() == 1.0
    assert dest.get_bottom() is None
    assert dest.get_right() is None
    assert dest.get_top() == 4.0


def test_fit_rectangle_type_is_fit_r() -> None:
    dest = PDPageFitRectangleDestination()
    assert dest.get_type() == "FitR"
