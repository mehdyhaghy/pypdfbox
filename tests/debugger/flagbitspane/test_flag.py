"""Tests for the abstract :class:`Flag` base."""

from __future__ import annotations

import pytest

from pypdfbox.debugger.flagbitspane.flag import Flag


def test_flag_is_abstract():
    with pytest.raises(TypeError):
        Flag()  # type: ignore[abstract]


def test_default_column_names():
    class _F(Flag):
        def get_flag_type(self) -> str:
            return ""

        def get_flag_value(self) -> str:
            return ""

        def get_flag_bits(self):
            return []

    assert _F().get_column_names() == ["Bit Position", "Name", "Set"]


@pytest.mark.parametrize(
    "value,bit,expected",
    [
        (0, 1, False),
        (1, 1, True),
        (2, 1, False),
        (2, 2, True),
        (0b1000_0000, 8, True),
        (0b1000_0000, 7, False),
        (0xFFFFFFFF, 32, True),
        (0, 32, False),
    ],
)
def test_is_flag_bit_set(value, bit, expected):
    assert Flag._is_flag_bit_set(value, bit) is expected
