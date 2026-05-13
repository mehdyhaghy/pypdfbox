"""Hand-written tests for :class:`pypdfbox.debugger.ui.ZoomMenu`."""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.ui.zoom_menu import ZoomMenu


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    ZoomMenu._reset_instance()
    yield
    ZoomMenu._reset_instance()


def test_construction_yields_eight_entries(tk_root: tk.Tk) -> None:
    menu = ZoomMenu.get_instance(master=tk_root)
    assert menu.get_menu().index("end") == len(ZoomMenu.ZOOMS) - 1
    # Default selection mirrors upstream (100% on a fresh instance).
    assert ZoomMenu.get_zoom_scale() == pytest.approx(1.0)


def test_singleton_returns_same_instance(tk_root: tk.Tk) -> None:
    first = ZoomMenu.get_instance(master=tk_root)
    second = ZoomMenu.get_instance(master=tk_root)
    assert first is second


def test_change_zoom_selection_updates_variable(tk_root: tk.Tk) -> None:
    menu = ZoomMenu.get_instance(master=tk_root)
    menu.change_zoom_selection(2.0)
    assert ZoomMenu.get_zoom_scale() == pytest.approx(2.0)
    menu.change_zoom_selection(0.25)
    assert ZoomMenu.get_zoom_scale() == pytest.approx(0.25)


def test_change_zoom_selection_unknown_value(tk_root: tk.Tk) -> None:
    menu = ZoomMenu.get_instance(master=tk_root)
    with pytest.raises(ValueError):
        menu.change_zoom_selection(0.33)


def test_is_zoom_menu_classifier() -> None:
    assert ZoomMenu.is_zoom_menu("100%")
    assert ZoomMenu.is_zoom_menu("25%")
    assert not ZoomMenu.is_zoom_menu("99%")
    assert not ZoomMenu.is_zoom_menu("hello")
    assert not ZoomMenu.is_zoom_menu("xyz%")


def test_page_and_image_zoom_state(tk_root: tk.Tk) -> None:
    menu = ZoomMenu.get_instance(master=tk_root)
    assert menu.get_page_zoom_scale() == pytest.approx(1.0)
    menu.set_page_zoom_scale(2.5)
    assert menu.get_page_zoom_scale() == pytest.approx(2.5)
    menu.set_image_zoom_scale(4.0)
    assert menu.get_image_zoom_scale() == pytest.approx(4.0)
    menu.reset_zoom()
    assert menu.get_page_zoom_scale() == pytest.approx(1.0)
    assert menu.get_image_zoom_scale() == pytest.approx(1.0)
    assert ZoomMenu.get_zoom_scale() == pytest.approx(1.0)


def test_click_radiobutton_updates_zoom(tk_root: tk.Tk) -> None:
    menu = ZoomMenu.get_instance(master=tk_root)
    tk_menu = menu.get_menu()
    # Invoke the second entry — index 1 corresponds to ZOOMS[1] = 50%.
    tk_menu.invoke(1)
    assert ZoomMenu.get_zoom_scale() == pytest.approx(ZoomMenu.ZOOMS[1] / 100.0)
