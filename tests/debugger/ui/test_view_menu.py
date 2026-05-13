"""Hand-written tests for :class:`pypdfbox.debugger.ui.ViewMenu`."""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
from pypdfbox.debugger.ui.rotation_menu import RotationMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.debugger.ui.zoom_menu import ZoomMenu


@pytest.fixture(autouse=True)
def _reset_singletons() -> None:
    ViewMenu._reset_instance()
    ZoomMenu._reset_instance()
    RotationMenu._reset_instance()
    RenderDestinationMenu._reset_instance()
    yield
    ViewMenu._reset_instance()
    ZoomMenu._reset_instance()
    RotationMenu._reset_instance()
    RenderDestinationMenu._reset_instance()


def test_construction_wires_three_cascades(tk_root: tk.Tk) -> None:
    view = ViewMenu(master=tk_root)
    tk_menu = view.get_menu()
    # Three cascade entries + 1 separator + 1 checkbutton = indices 0..4.
    assert tk_menu.index("end") == 4
    assert tk_menu.type(0) == "cascade"
    assert tk_menu.type(1) == "cascade"
    assert tk_menu.type(2) == "cascade"
    assert tk_menu.type(3) == "separator"
    assert tk_menu.type(4) == "checkbutton"


def test_singleton(tk_root: tk.Tk) -> None:
    a = ViewMenu.get_instance(master=tk_root)
    b = ViewMenu.get_instance(master=tk_root)
    assert a is b


def test_allow_subsampling_default_off(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    assert ViewMenu.is_allow_subsampling() is False


def test_allow_subsampling_toggle(tk_root: tk.Tk) -> None:
    view = ViewMenu.get_instance(master=tk_root)
    # The checkbutton sits at index 4 (after three cascades + separator).
    view.get_menu().invoke(4)
    assert ViewMenu.is_allow_subsampling() is True
    view.get_menu().invoke(4)
    assert ViewMenu.is_allow_subsampling() is False


def test_view_menu_starts_with_submenus_disabled(tk_root: tk.Tk) -> None:
    ViewMenu.get_instance(master=tk_root)
    # Construction sets each sub-menu's entries to disabled.
    assert ZoomMenu.get_instance().get_menu().entrycget(0, "state") == "disabled"
    assert RotationMenu.get_instance().get_menu().entrycget(0, "state") == "disabled"
    assert (
        RenderDestinationMenu.get_instance().get_menu().entrycget(0, "state")
        == "disabled"
    )
