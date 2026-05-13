"""Tests for :class:`IndexedColorant`.

Pure data-record tests — no Tk required.
"""

from __future__ import annotations

import pytest

from pypdfbox.debugger.colorpane.indexed_colorant import IndexedColorant


def test_default_state_index_is_zero_rgb_unset() -> None:
    colorant = IndexedColorant()
    assert colorant.get_index() == 0
    # Calling get_color before set_rgb_values must raise.
    with pytest.raises(ValueError):
        colorant.get_color()


def test_set_and_get_index_round_trip() -> None:
    colorant = IndexedColorant()
    colorant.set_index(42)
    assert colorant.get_index() == 42


def test_set_rgb_values_then_get_color_returns_tuple() -> None:
    colorant = IndexedColorant()
    colorant.set_rgb_values([1.0, 0.5, 0.0])
    assert colorant.get_color() == (1.0, 0.5, 0.0)


def test_get_rgb_values_string_scales_to_byte_range() -> None:
    colorant = IndexedColorant()
    colorant.set_rgb_values([1.0, 0.5, 0.0])
    # 1.0 * 255 = 255, 0.5 * 255 = 127 (int trunc), 0.0 * 255 = 0
    assert colorant.get_rgb_values_string() == "255, 127, 0"


def test_get_rgb_values_string_with_no_data_returns_empty() -> None:
    assert IndexedColorant().get_rgb_values_string() == ""


def test_set_rgb_values_defensive_copies_input() -> None:
    src = [0.1, 0.2, 0.3]
    colorant = IndexedColorant()
    colorant.set_rgb_values(src)
    src[0] = 0.99  # mutate caller's list
    # Internal state must not be affected.
    assert colorant.get_color() == (0.1, 0.2, 0.3)
