from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDTransition,
    PDTransitionDimension,
    PDTransitionDirection,
    PDTransitionMotion,
)


def test_motion_constants_on_pd_transition() -> None:
    assert PDTransition.MOTION_INWARD == "I"
    assert PDTransition.MOTION_OUTWARD == "O"


def test_dimension_constants_on_pd_transition() -> None:
    assert PDTransition.DIMENSION_HORIZONTAL == "H"
    assert PDTransition.DIMENSION_VERTICAL == "V"


def test_motion_round_trip_with_class_constants() -> None:
    transition = PDTransition()
    transition.set_motion(PDTransition.MOTION_OUTWARD)
    assert transition.get_motion() == "O"
    transition.set_motion(PDTransition.MOTION_INWARD)
    assert transition.get_motion() == "I"


def test_motion_round_trip_with_enum_constants() -> None:
    transition = PDTransition()
    transition.set_motion(PDTransitionMotion.O)
    assert transition.get_motion() == PDTransitionMotion.O
    transition.set_motion(PDTransitionMotion.I)
    assert transition.get_motion() == PDTransitionMotion.I


def test_dimension_round_trip_with_class_constants() -> None:
    transition = PDTransition()
    transition.set_dimension(PDTransition.DIMENSION_VERTICAL)
    assert transition.get_dimension() == "V"
    transition.set_dimension(PDTransition.DIMENSION_HORIZONTAL)
    assert transition.get_dimension() == "H"


def test_dimension_round_trip_with_enum_constants() -> None:
    transition = PDTransition()
    transition.set_dimension(PDTransitionDimension.V)
    assert transition.get_dimension() == PDTransitionDimension.V
    transition.set_dimension(PDTransitionDimension.H)
    assert transition.get_dimension() == PDTransitionDimension.H


def test_duration_default_is_one() -> None:
    transition = PDTransition(COSDictionary())
    assert transition.get_duration() == 1


def test_duration_round_trip() -> None:
    transition = PDTransition()
    transition.set_duration(3.25)
    assert transition.get_duration() == 3.25
    transition.set_duration(0.0)
    assert transition.get_duration() == 0.0


def test_scale_default_is_one() -> None:
    transition = PDTransition(COSDictionary())
    assert transition.get_scale() == 1.0


def test_scale_round_trip() -> None:
    transition = PDTransition()
    transition.set_scale(0.75)
    assert transition.get_scale() == 0.75
    transition.set_scale(2.0)
    assert transition.get_scale() == 2.0


def test_scale_and_fly_scale_share_storage() -> None:
    transition = PDTransition()
    transition.set_scale(0.5)
    assert transition.get_fly_scale() == 0.5
    transition.set_fly_scale(0.25)
    assert transition.get_scale() == 0.25


def test_is_fly_area_to_show_matches_getter() -> None:
    transition = PDTransition()
    assert transition.is_fly_area_to_show() is False
    transition.set_fly_area_to_show(True)
    assert transition.is_fly_area_to_show() is True
    assert transition.get_fly_area_to_show() is True


def test_is_fly_area_opaque_default_is_false() -> None:
    # Upstream-name accessor: matches PDFBox `isFlyAreaOpaque()` default.
    transition = PDTransition(COSDictionary())
    assert transition.is_fly_area_opaque() is False


def test_set_fly_area_opaque_round_trip() -> None:
    transition = PDTransition()
    transition.set_fly_area_opaque(True)
    assert transition.is_fly_area_opaque() is True
    transition.set_fly_area_opaque(False)
    assert transition.is_fly_area_opaque() is False


def test_fly_area_opaque_and_to_show_share_storage() -> None:
    # Both accessor families read/write the same /B entry — they're aliases.
    transition = PDTransition()
    transition.set_fly_area_opaque(True)
    assert transition.is_fly_area_to_show() is True
    assert transition.get_fly_area_to_show() is True
    transition.set_fly_area_to_show(False)
    assert transition.is_fly_area_opaque() is False


def test_get_direction_cos_default_is_cos_integer_zero() -> None:
    # Upstream `getDirection()` returns COSInteger.ZERO when /Di is absent.
    transition = PDTransition(COSDictionary())
    raw = transition.get_direction_cos()
    assert isinstance(raw, COSInteger)
    assert raw.value == 0


def test_get_direction_cos_returns_cos_integer_when_int_set() -> None:
    transition = PDTransition()
    transition.set_direction(PDTransitionDirection.RIGHT_TO_LEFT)
    raw = transition.get_direction_cos()
    assert isinstance(raw, COSInteger)
    assert raw.value == 180


def test_get_direction_cos_returns_cos_name_when_none_set() -> None:
    transition = PDTransition()
    transition.set_direction(PDTransitionDirection.NONE)
    raw = transition.get_direction_cos()
    assert isinstance(raw, COSName)
    assert raw == COSName.get_pdf_name("None")
