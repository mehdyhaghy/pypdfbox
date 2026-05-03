"""Hand-written tests for ``PDPageFitRectangleDestination`` (``/FitR``)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitRectangleDestination,
)


def test_default_construction_writes_fit_r_type() -> None:
    dest = PDPageFitRectangleDestination()
    assert dest.get_type() == PDPageFitRectangleDestination.TYPE
    assert dest.get_type() == "FitR"


def test_inherits_pd_page_destination() -> None:
    dest = PDPageFitRectangleDestination()
    assert isinstance(dest, PDPageDestination)


def test_default_edges_are_none() -> None:
    dest = PDPageFitRectangleDestination()
    assert dest.get_left() is None
    assert dest.get_bottom() is None
    assert dest.get_right() is None
    assert dest.get_top() is None
    assert dest.is_left_unset() is True
    assert dest.is_bottom_unset() is True
    assert dest.is_right_unset() is True
    assert dest.is_top_unset() is True
    assert dest.is_complete() is False


def test_edges_round_trip_individually() -> None:
    dest = PDPageFitRectangleDestination()

    dest.set_left(10.0)
    dest.set_bottom(20.0)
    dest.set_right(30.5)
    dest.set_top(40.5)

    assert dest.get_left() == 10.0
    assert dest.get_bottom() == 20.0
    assert dest.get_right() == 30.5
    assert dest.get_top() == 40.5
    assert dest.is_complete() is True


def test_set_rect_writes_all_four_edges() -> None:
    dest = PDPageFitRectangleDestination()

    dest.set_rect(1.0, 2.0, 3.0, 4.0)

    assert dest.get_rect() == (1.0, 2.0, 3.0, 4.0)
    assert dest.is_complete() is True


def test_set_rect_with_none_writes_cos_null() -> None:
    dest = PDPageFitRectangleDestination()
    dest.set_rect(1.0, 2.0, 3.0, 4.0)

    dest.set_rect(None, 2.0, None, 4.0)

    assert dest.get_rect() == (None, 2.0, None, 4.0)
    assert dest.is_left_unset() is True
    assert dest.is_bottom_unset() is False
    assert dest.is_right_unset() is True
    assert dest.is_top_unset() is False
    assert dest.is_complete() is False


def test_get_rect_default_is_all_none() -> None:
    dest = PDPageFitRectangleDestination()
    assert dest.get_rect() == (None, None, None, None)


def test_clear_helpers_write_cos_null() -> None:
    dest = PDPageFitRectangleDestination()
    dest.set_rect(1.0, 2.0, 3.0, 4.0)

    dest.clear_left()
    dest.clear_bottom()
    dest.clear_right()
    dest.clear_top()

    arr = dest.get_cos_array()
    assert arr.get(2) is COSNull.NULL
    assert arr.get(3) is COSNull.NULL
    assert arr.get(4) is COSNull.NULL
    assert arr.get(5) is COSNull.NULL
    assert dest.get_rect() == (None, None, None, None)


def test_clear_grows_array_when_short() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("FitR")])
    dest = PDPageFitRectangleDestination(arr)

    dest.clear_top()
    assert dest.get_cos_array().size() >= 6
    assert dest.get_cos_array().get(5) is COSNull.NULL


def test_constructed_from_existing_array_preserves_edges() -> None:
    arr = COSArray(
        [
            COSInteger.get(5),
            COSName.get_pdf_name("FitR"),
            COSFloat(10.0),
            COSFloat(20.0),
            COSFloat(30.0),
            COSFloat(40.0),
        ]
    )
    dest = PDPageFitRectangleDestination(arr)

    assert dest.get_page_number() == 5
    assert dest.get_rect() == (10.0, 20.0, 30.0, 40.0)
    assert dest.is_complete() is True


def test_int_edges_returned_as_float() -> None:
    arr = COSArray(
        [
            COSInteger.get(0),
            COSName.get_pdf_name("FitR"),
            COSInteger.get(10),
            COSInteger.get(20),
            COSInteger.get(30),
            COSInteger.get(40),
        ]
    )
    dest = PDPageFitRectangleDestination(arr)

    assert dest.get_rect() == (10.0, 20.0, 30.0, 40.0)
    for unset in (
        dest.is_left_unset(),
        dest.is_bottom_unset(),
        dest.is_right_unset(),
        dest.is_top_unset(),
    ):
        assert unset is False


def test_partial_set_then_clear() -> None:
    dest = PDPageFitRectangleDestination()
    dest.set_left(10.0)
    dest.set_top(40.0)

    assert dest.is_left_unset() is False
    assert dest.is_top_unset() is False
    assert dest.is_bottom_unset() is True
    assert dest.is_right_unset() is True
    assert dest.is_complete() is False

    dest.clear_left()
    assert dest.is_left_unset() is True
    assert dest.get_left() is None
    # top remains intact
    assert dest.get_top() == 40.0


def test_set_page_number_round_trip() -> None:
    dest = PDPageFitRectangleDestination()
    dest.set_page_number(9)
    assert dest.get_page_number() == 9
