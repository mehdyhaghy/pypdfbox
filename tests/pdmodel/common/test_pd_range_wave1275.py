"""Wave 1275 round-out: ``PDRange.to_string()`` explicit method."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat
from pypdfbox.pdmodel.common.pd_range import PDRange


def test_to_string_default_zero_one() -> None:
    rng = PDRange()
    # Mirrors upstream ``PDRange.toString()`` (PDRange.java line 137):
    # ``PDRange{<min>, <max>}``.
    assert rng.to_string() == "PDRange{0.0, 1.0}"


def test_to_string_uses_pair_offset() -> None:
    arr = COSArray()
    for v in (-1.5, 1.5, 0.0, 2.0):
        arr.add(COSFloat(v))
    second = PDRange(arr, 1)
    assert second.to_string() == "PDRange{0.0, 2.0}"


def test_to_string_matches_str() -> None:
    rng = PDRange()
    assert rng.to_string() == str(rng)
