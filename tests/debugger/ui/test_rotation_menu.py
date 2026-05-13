"""Hand-written tests for :class:`pypdfbox.debugger.ui.RotationMenu`."""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.ui.rotation_menu import RotationMenu


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    RotationMenu._reset_instance()
    yield
    RotationMenu._reset_instance()


def test_construction_yields_four_entries(tk_root: tk.Tk) -> None:
    menu = RotationMenu(master=tk_root)
    assert menu.get_menu().index("end") == 3
    # Default selection is 0°.
    assert RotationMenu.get_rotation_degrees() == 0


def test_singleton(tk_root: tk.Tk) -> None:
    a = RotationMenu.get_instance(master=tk_root)
    b = RotationMenu.get_instance(master=tk_root)
    assert a is b


def test_set_rotation_selection_round_trip(tk_root: tk.Tk) -> None:
    menu = RotationMenu.get_instance(master=tk_root)
    menu.set_rotation_selection(RotationMenu.ROTATE_180_DEGREES)
    assert RotationMenu.get_rotation_degrees() == 180
    menu.set_rotation_selection(RotationMenu.ROTATE_270_DEGREES)
    assert RotationMenu.get_rotation_degrees() == 270


def test_set_rotation_selection_rejects_bad_value(tk_root: tk.Tk) -> None:
    menu = RotationMenu.get_instance(master=tk_root)
    with pytest.raises(ValueError):
        menu.set_rotation_selection("45°")


def test_is_rotation_menu_classifier() -> None:
    assert RotationMenu.is_rotation_menu(RotationMenu.ROTATE_0_DEGREES)
    assert RotationMenu.is_rotation_menu(RotationMenu.ROTATE_90_DEGREES)
    assert not RotationMenu.is_rotation_menu("45°")
    assert not RotationMenu.is_rotation_menu("")


def test_get_rotation_degrees_for_string() -> None:
    assert RotationMenu.get_rotation_degrees_for(RotationMenu.ROTATE_0_DEGREES) == 0
    assert RotationMenu.get_rotation_degrees_for(RotationMenu.ROTATE_90_DEGREES) == 90
    assert RotationMenu.get_rotation_degrees_for(RotationMenu.ROTATE_180_DEGREES) == 180
    assert RotationMenu.get_rotation_degrees_for(RotationMenu.ROTATE_270_DEGREES) == 270
    with pytest.raises(ValueError):
        RotationMenu.get_rotation_degrees_for("bogus")


def test_click_radiobutton_updates_rotation(tk_root: tk.Tk) -> None:
    menu = RotationMenu.get_instance(master=tk_root)
    menu.get_menu().invoke(2)  # 180°
    assert RotationMenu.get_rotation_degrees() == 180
