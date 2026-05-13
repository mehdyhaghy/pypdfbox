"""Hand-written tests for :class:`pypdfbox.debugger.ui.ImageTypeMenu`."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
from pypdfbox.rendering.image_type import ImageType


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    ImageTypeMenu._reset_for_testing()
    yield
    ImageTypeMenu._reset_for_testing()


def test_construction_yields_four_entries(tk_root: tk.Tk) -> None:
    menu = ImageTypeMenu.get_instance(master=tk_root)
    assert menu.get_menu().index("end") == 3  # four entries, last index = 3
    # Default selection mirrors upstream (RGB on a fresh instance).
    assert ImageTypeMenu.get_image_type() is ImageType.RGB


def test_singleton_returns_same_instance(tk_root: tk.Tk) -> None:
    first = ImageTypeMenu.get_instance(master=tk_root)
    second = ImageTypeMenu.get_instance(master=tk_root)
    assert first is second


def test_set_image_type_selection_updates_variable(tk_root: tk.Tk) -> None:
    menu = ImageTypeMenu.get_instance(master=tk_root)
    menu.set_image_type_selection(ImageTypeMenu.IMAGETYPE_ARGB)
    assert ImageTypeMenu.get_image_type() is ImageType.ARGB
    menu.set_image_type_selection(ImageTypeMenu.IMAGETYPE_GRAY)
    assert ImageTypeMenu.get_image_type() is ImageType.GRAY
    menu.set_image_type_selection(ImageTypeMenu.IMAGETYPE_BITONAL)
    assert ImageTypeMenu.get_image_type() is ImageType.BINARY


def test_set_image_type_selection_invalid(tk_root: tk.Tk) -> None:
    menu = ImageTypeMenu.get_instance(master=tk_root)
    with pytest.raises(ValueError):
        menu.set_image_type_selection("CMYK")


def test_is_image_type_menu_classifier() -> None:
    assert ImageTypeMenu.is_image_type_menu("RGB")
    assert ImageTypeMenu.is_image_type_menu("ARGB")
    assert ImageTypeMenu.is_image_type_menu("Gray")
    assert ImageTypeMenu.is_image_type_menu("Bitonal")
    assert not ImageTypeMenu.is_image_type_menu("CMYK")
    assert not ImageTypeMenu.is_image_type_menu("")


def test_get_image_type_by_action_command() -> None:
    assert ImageTypeMenu.get_image_type("RGB") is ImageType.RGB
    assert ImageTypeMenu.get_image_type("ARGB") is ImageType.ARGB
    assert ImageTypeMenu.get_image_type("Gray") is ImageType.GRAY
    assert ImageTypeMenu.get_image_type("Bitonal") is ImageType.BINARY


def test_get_image_type_unknown_action_command() -> None:
    with pytest.raises(ValueError):
        ImageTypeMenu.get_image_type("CMYK")


def test_click_radiobutton_updates_selection(tk_root: tk.Tk) -> None:
    menu = ImageTypeMenu.get_instance(master=tk_root)
    tk_menu = menu.get_menu()
    # Index 1 corresponds to ARGB (second of the four entries).
    tk_menu.invoke(1)
    assert ImageTypeMenu.get_image_type() is ImageType.ARGB
