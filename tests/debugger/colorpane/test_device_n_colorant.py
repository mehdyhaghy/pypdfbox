"""Tests for :class:`DeviceNColorant`.

Pure data-record tests — no Tk required.
"""

from __future__ import annotations

from pypdfbox.debugger.colorpane.device_n_colorant import DeviceNColorant


def test_default_state_is_all_none() -> None:
    colorant = DeviceNColorant()
    assert colorant.get_name() is None
    assert colorant.get_maximum() is None
    assert colorant.get_minimum() is None


def test_set_and_get_name_round_trip() -> None:
    colorant = DeviceNColorant()
    colorant.set_name("Cyan")
    assert colorant.get_name() == "Cyan"


def test_set_and_get_maximum_round_trip() -> None:
    colorant = DeviceNColorant()
    colorant.set_maximum((1.0, 0.5, 0.0))
    assert colorant.get_maximum() == (1.0, 0.5, 0.0)


def test_set_and_get_minimum_round_trip() -> None:
    colorant = DeviceNColorant()
    colorant.set_minimum((0.0, 0.0, 0.0))
    assert colorant.get_minimum() == (0.0, 0.0, 0.0)


def test_independent_setters() -> None:
    a = DeviceNColorant()
    b = DeviceNColorant()
    a.set_name("Cyan")
    b.set_name("Magenta")
    assert a.get_name() == "Cyan"
    assert b.get_name() == "Magenta"
