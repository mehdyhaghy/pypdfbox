from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDTransition,
    PDTransitionDimension,
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
