from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDTransition,
    PDTransitionDimension,
    PDTransitionDirection,
    PDTransitionMotion,
    PDTransitionStyle,
)


def test_default_transition_has_type_trans_and_replace_style() -> None:
    transition = PDTransition()
    cos = transition.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("Type")) == "Trans"
    assert cos.get_name(COSName.get_pdf_name("S")) == PDTransitionStyle.R
    assert transition.get_style() == "R"


def test_explicit_style_in_constructor_round_trips() -> None:
    transition = PDTransition(style=PDTransitionStyle.WIPE)
    assert transition.get_style() == "Wipe"


def test_wrap_existing_dictionary_preserves_identity() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), PDTransitionStyle.FLY)
    transition = PDTransition(raw)
    assert transition.get_cos_object() is raw
    assert transition.get_style() == "Fly"


def test_set_style_round_trip() -> None:
    transition = PDTransition()
    transition.set_style(PDTransitionStyle.GLITTER)
    assert transition.get_style() == "Glitter"


def test_default_values_match_upstream() -> None:
    transition = PDTransition(COSDictionary())
    assert transition.get_style() == PDTransitionStyle.R
    assert transition.get_duration() == 1
    assert transition.get_motion() == PDTransitionMotion.I
    assert transition.get_dimension() == PDTransitionDimension.H
    assert transition.get_direction() == PDTransitionDirection.LEFT_TO_RIGHT
    assert transition.get_fly_scale() == 1
    assert transition.get_fly_area_to_show() is False


def test_duration_round_trip() -> None:
    transition = PDTransition()
    transition.set_duration(2.5)
    assert transition.get_duration() == 2.5


def test_motion_round_trip() -> None:
    transition = PDTransition()
    transition.set_motion(PDTransitionMotion.O)
    assert transition.get_motion() == "O"


def test_dimension_round_trip() -> None:
    transition = PDTransition()
    transition.set_dimension(PDTransitionDimension.V)
    assert transition.get_dimension() == "V"


def test_direction_round_trip_int() -> None:
    transition = PDTransition()
    transition.set_direction(PDTransitionDirection.TOP_LEFT_TO_BOTTOM_RIGHT)
    assert transition.get_direction() == 315


def test_direction_none_writes_name_and_reads_back_sentinel() -> None:
    transition = PDTransition()
    transition.set_direction(PDTransitionDirection.NONE)
    item = transition.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Di"))
    assert isinstance(item, COSName)
    assert item == COSName.get_pdf_name("None")
    assert transition.get_direction() == PDTransitionDirection.NONE


def test_direction_name_none_in_existing_dict_parses_to_sentinel() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("Di"), "None")
    transition = PDTransition(raw)
    assert transition.get_direction() == PDTransitionDirection.NONE


def test_fly_scale_round_trip() -> None:
    transition = PDTransition()
    transition.set_fly_scale(0.5)
    assert transition.get_fly_scale() == 0.5


def test_fly_area_to_show_round_trip() -> None:
    transition = PDTransition()
    transition.set_fly_area_to_show(True)
    assert transition.get_fly_area_to_show() is True
    transition.set_fly_area_to_show(False)
    assert transition.get_fly_area_to_show() is False


def test_transition_style_constants() -> None:
    assert PDTransitionStyle.SPLIT == "Split"
    assert PDTransitionStyle.BLINDS == "Blinds"
    assert PDTransitionStyle.BOX == "Box"
    assert PDTransitionStyle.WIPE == "Wipe"
    assert PDTransitionStyle.DISSOLVE == "Dissolve"
    assert PDTransitionStyle.GLITTER == "Glitter"
    assert PDTransitionStyle.R == "R"
    assert PDTransitionStyle.FLY == "Fly"
    assert PDTransitionStyle.PUSH == "Push"
    assert PDTransitionStyle.COVER == "Cover"
    assert PDTransitionStyle.UNCOVER == "Uncover"
    assert PDTransitionStyle.FADE == "Fade"


def test_transition_motion_dimension_direction_constants() -> None:
    assert PDTransitionMotion.I == "I"
    assert PDTransitionMotion.O == "O"
    assert PDTransitionDimension.H == "H"
    assert PDTransitionDimension.V == "V"
    assert PDTransitionDirection.LEFT_TO_RIGHT == 0
    assert PDTransitionDirection.BOTTOM_TO_TOP == 90
    assert PDTransitionDirection.RIGHT_TO_LEFT == 180
    assert PDTransitionDirection.TOP_TO_BOTTOM == 270
    assert PDTransitionDirection.TOP_LEFT_TO_BOTTOM_RIGHT == 315
    assert PDTransitionDirection.NONE == -1
