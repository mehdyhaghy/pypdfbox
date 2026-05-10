from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.pagenavigation import PDTransitionStyle

# ---------- values() ----------


def test_values_lists_all_twelve_styles_in_spec_order() -> None:
    # Order matches PDF 32000-1:2008 table 162 / upstream enum declaration.
    assert PDTransitionStyle.values() == (
        "Split",
        "Blinds",
        "Box",
        "Wipe",
        "Dissolve",
        "Glitter",
        "R",
        "Fly",
        "Push",
        "Cover",
        "Uncover",
        "Fade",
    )


def test_values_returns_tuple_so_callers_cannot_mutate() -> None:
    # Tuple is immutable; rules out a class of "I edited the enum" bugs.
    assert isinstance(PDTransitionStyle.values(), tuple)


def test_values_contains_each_constant() -> None:
    every = PDTransitionStyle.values()
    for constant in (
        PDTransitionStyle.SPLIT,
        PDTransitionStyle.BLINDS,
        PDTransitionStyle.BOX,
        PDTransitionStyle.WIPE,
        PDTransitionStyle.DISSOLVE,
        PDTransitionStyle.GLITTER,
        PDTransitionStyle.R,
        PDTransitionStyle.FLY,
        PDTransitionStyle.PUSH,
        PDTransitionStyle.COVER,
        PDTransitionStyle.UNCOVER,
        PDTransitionStyle.FADE,
    ):
        assert constant in every


# ---------- value_of ----------


@pytest.mark.parametrize(
    "name",
    [
        "Split",
        "Blinds",
        "Box",
        "Wipe",
        "Dissolve",
        "Glitter",
        "R",
        "Fly",
        "Push",
        "Cover",
        "Uncover",
        "Fade",
    ],
)
def test_value_of_accepts_every_spec_style(name: str) -> None:
    assert PDTransitionStyle.value_of(name) == name


def test_value_of_unknown_name_raises_value_error() -> None:
    with pytest.raises(ValueError):
        PDTransitionStyle.value_of("Spiral")


def test_value_of_is_case_sensitive_like_java_enum() -> None:
    # Upstream Java enum is case-sensitive; lower-case "wipe" is not "Wipe".
    with pytest.raises(ValueError):
        PDTransitionStyle.value_of("wipe")


def test_value_of_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        PDTransitionStyle.value_of("")


# ---------- is_valid ----------


def test_is_valid_recognises_every_spec_style() -> None:
    for name in PDTransitionStyle.values():
        assert PDTransitionStyle.is_valid(name) is True


def test_is_valid_rejects_unknown() -> None:
    assert PDTransitionStyle.is_valid("Bogus") is False


def test_is_valid_rejects_none() -> None:
    assert PDTransitionStyle.is_valid(None) is False


def test_is_valid_is_case_sensitive() -> None:
    assert PDTransitionStyle.is_valid("split") is False
    assert PDTransitionStyle.is_valid("FLY") is False


# ---------- supports_motion ----------


@pytest.mark.parametrize("name", ["Split", "Blinds", "Fly"])
def test_supports_motion_true_for_split_blinds_fly(name: str) -> None:
    assert PDTransitionStyle.supports_motion(name) is True


@pytest.mark.parametrize(
    "name", ["Box", "Wipe", "Dissolve", "Glitter", "R", "Push", "Cover", "Uncover", "Fade"]
)
def test_supports_motion_false_for_other_styles(name: str) -> None:
    assert PDTransitionStyle.supports_motion(name) is False


def test_supports_motion_false_for_none_and_unknown() -> None:
    assert PDTransitionStyle.supports_motion(None) is False
    assert PDTransitionStyle.supports_motion("Bogus") is False


# ---------- supports_dimension ----------


@pytest.mark.parametrize("name", ["Split", "Blinds"])
def test_supports_dimension_true_for_split_blinds(name: str) -> None:
    assert PDTransitionStyle.supports_dimension(name) is True


@pytest.mark.parametrize(
    "name",
    ["Box", "Wipe", "Dissolve", "Glitter", "R", "Fly", "Push", "Cover", "Uncover", "Fade"],
)
def test_supports_dimension_false_for_other_styles(name: str) -> None:
    assert PDTransitionStyle.supports_dimension(name) is False


def test_supports_dimension_false_for_none() -> None:
    assert PDTransitionStyle.supports_dimension(None) is False


# ---------- supports_direction ----------


@pytest.mark.parametrize(
    "name", ["Wipe", "Glitter", "Fly", "Cover", "Uncover", "Push"]
)
def test_supports_direction_true_for_wipe_glitter_fly_cover_uncover_push(
    name: str,
) -> None:
    assert PDTransitionStyle.supports_direction(name) is True


@pytest.mark.parametrize(
    "name", ["Split", "Blinds", "Box", "Dissolve", "R", "Fade"]
)
def test_supports_direction_false_for_other_styles(name: str) -> None:
    assert PDTransitionStyle.supports_direction(name) is False


def test_supports_direction_false_for_none() -> None:
    assert PDTransitionStyle.supports_direction(None) is False


# ---------- supports_fly_scale ----------


def test_supports_fly_scale_true_only_for_fly() -> None:
    assert PDTransitionStyle.supports_fly_scale("Fly") is True


@pytest.mark.parametrize(
    "name",
    [
        "Split",
        "Blinds",
        "Box",
        "Wipe",
        "Dissolve",
        "Glitter",
        "R",
        "Push",
        "Cover",
        "Uncover",
        "Fade",
    ],
)
def test_supports_fly_scale_false_for_non_fly_styles(name: str) -> None:
    assert PDTransitionStyle.supports_fly_scale(name) is False


def test_supports_fly_scale_false_for_none() -> None:
    assert PDTransitionStyle.supports_fly_scale(None) is False
