"""Coverage-boost tests for ``PDTransitionDirection``.

Targets ``values()`` and ``get_cos_base()`` which are unreached by the
existing transition test suite.
"""

from __future__ import annotations

from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition_direction import (
    PDTransitionDirection,
)


def test_values_returns_all_six_declared_directions() -> None:
    vals = PDTransitionDirection.values()
    assert vals == (0, 90, 180, 270, 315, -1)
    assert len(vals) == 6


def test_values_includes_none_sentinel() -> None:
    assert PDTransitionDirection.NONE in PDTransitionDirection.values()


def test_get_cos_base_for_none_returns_cos_name_none() -> None:
    obj = PDTransitionDirection.get_cos_base(PDTransitionDirection.NONE)
    assert isinstance(obj, COSName)
    assert obj == COSName.get_pdf_name("None")


def test_get_cos_base_for_zero_returns_cos_integer_zero() -> None:
    obj = PDTransitionDirection.get_cos_base(PDTransitionDirection.LEFT_TO_RIGHT)
    assert isinstance(obj, COSInteger)
    assert obj.int_value() == 0


def test_get_cos_base_for_ninety_returns_cos_integer_ninety() -> None:
    obj = PDTransitionDirection.get_cos_base(PDTransitionDirection.BOTTOM_TO_TOP)
    assert isinstance(obj, COSInteger)
    assert obj.int_value() == 90


def test_get_cos_base_for_one_eighty_returns_cos_integer_one_eighty() -> None:
    obj = PDTransitionDirection.get_cos_base(PDTransitionDirection.RIGHT_TO_LEFT)
    assert isinstance(obj, COSInteger)
    assert obj.int_value() == 180


def test_get_cos_base_for_two_seventy_returns_cos_integer_two_seventy() -> None:
    obj = PDTransitionDirection.get_cos_base(PDTransitionDirection.TOP_TO_BOTTOM)
    assert isinstance(obj, COSInteger)
    assert obj.int_value() == 270


def test_get_cos_base_for_three_fifteen_returns_cos_integer_three_fifteen() -> None:
    obj = PDTransitionDirection.get_cos_base(
        PDTransitionDirection.TOP_LEFT_TO_BOTTOM_RIGHT
    )
    assert isinstance(obj, COSInteger)
    assert obj.int_value() == 315


def test_get_cos_base_for_arbitrary_int_passes_through() -> None:
    # The class doesn't validate the int — non-standard values still
    # round-trip as COSInteger so PDTransition can carry custom values.
    obj = PDTransitionDirection.get_cos_base(45)
    assert isinstance(obj, COSInteger)
    assert obj.int_value() == 45
