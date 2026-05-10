"""Wave 1273 round-out: ``PDLineDashPattern.to_string()`` explicit method."""

from __future__ import annotations

from pypdfbox.cos import COSArray
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern


def test_to_string_default() -> None:
    # Mirrors upstream ``PDLineDashPattern.toString`` for the empty form.
    pattern = PDLineDashPattern()
    assert pattern.to_string() == "PDLineDashPattern{array=[], phase=0}"


def test_to_string_populated() -> None:
    array = COSArray()
    array.set_float_array([3, 2])
    pattern = PDLineDashPattern(array, 1)
    # Java's ``Arrays.toString(float[])`` formats integral floats as
    # ``3.0``, not ``3`` — match that.
    assert pattern.to_string() == "PDLineDashPattern{array=[3.0, 2.0], phase=1}"


def test_to_string_matches_str() -> None:
    array = COSArray()
    array.set_float_array([4.5, 6.5])
    pattern = PDLineDashPattern(array, 2)
    assert pattern.to_string() == str(pattern)
