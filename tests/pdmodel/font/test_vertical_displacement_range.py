"""Tests for :mod:`pypdfbox.pdmodel.font.vertical_displacement_range`.

The upstream class is a private nested helper of :class:`PDCIDFont`. We
cover the three accessors plus ``range_matches`` boundaries.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.vertical_displacement_range import (
    VerticalDisplacementRange,
)


def test_range_matches_inclusive_bounds() -> None:
    rng = VerticalDisplacementRange(0x100, 0x10F, (0, 0), -1000.0)
    assert rng.range_matches(0x100)
    assert rng.range_matches(0x10F)
    assert rng.range_matches(0x108)
    assert not rng.range_matches(0xFF)
    assert not rng.range_matches(0x110)


def test_accessors_return_constructor_values() -> None:
    vector = (500, -200)
    rng = VerticalDisplacementRange(1, 10, vector, -750.0)
    assert rng.range_start == 1
    assert rng.range_end == 10
    assert rng.get_position_vector() is vector
    assert rng.get_vertical_displacement() == -750.0


def test_repr_includes_all_fields() -> None:
    rng = VerticalDisplacementRange(0x10, 0x20, (1, 2), -42.5)
    text = repr(rng)
    assert "0x10" not in text  # we use decimal in repr
    assert "16" in text
    assert "32" in text
    assert "-42.5" in text
