"""Hand-written tests for :class:`pypdfbox.debugger.ui.RenderDestinationMenu`."""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
from pypdfbox.rendering.render_destination import RenderDestination


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    RenderDestinationMenu._reset_instance()
    yield
    RenderDestinationMenu._reset_instance()


def test_construction_yields_three_entries(tk_root: tk.Tk) -> None:
    menu = RenderDestinationMenu(master=tk_root)
    assert menu.get_menu().index("end") == 2
    # Default selection mirrors upstream (EXPORT).
    assert RenderDestinationMenu.get_render_destination() is RenderDestination.EXPORT


def test_singleton(tk_root: tk.Tk) -> None:
    a = RenderDestinationMenu.get_instance(master=tk_root)
    b = RenderDestinationMenu.get_instance(master=tk_root)
    assert a is b


def test_set_render_destination_selection_round_trip(tk_root: tk.Tk) -> None:
    menu = RenderDestinationMenu.get_instance(master=tk_root)
    menu.set_render_destination_selection(RenderDestinationMenu.RENDER_DESTINATION_PRINT)
    assert RenderDestinationMenu.get_render_destination() is RenderDestination.PRINT
    menu.set_render_destination_selection(RenderDestinationMenu.RENDER_DESTINATION_VIEW)
    assert RenderDestinationMenu.get_render_destination() is RenderDestination.VIEW


def test_set_render_destination_rejects_unknown_label(tk_root: tk.Tk) -> None:
    menu = RenderDestinationMenu.get_instance(master=tk_root)
    with pytest.raises(ValueError):
        menu.set_render_destination_selection("Bogus")


def test_is_render_destination_menu_classifier() -> None:
    assert RenderDestinationMenu.is_render_destination_menu("Export")
    assert RenderDestinationMenu.is_render_destination_menu("Print")
    assert RenderDestinationMenu.is_render_destination_menu("View")
    assert not RenderDestinationMenu.is_render_destination_menu("Save")


def test_get_render_destination_for_label() -> None:
    assert (
        RenderDestinationMenu.get_render_destination_for("Export")
        is RenderDestination.EXPORT
    )
    assert (
        RenderDestinationMenu.get_render_destination_for("Print")
        is RenderDestination.PRINT
    )
    assert (
        RenderDestinationMenu.get_render_destination_for("View")
        is RenderDestination.VIEW
    )
    with pytest.raises(ValueError):
        RenderDestinationMenu.get_render_destination_for("Unknown")


def test_click_radiobutton_updates_destination(tk_root: tk.Tk) -> None:
    menu = RenderDestinationMenu.get_instance(master=tk_root)
    menu.get_menu().invoke(1)  # PRINT
    assert RenderDestinationMenu.get_render_destination() is RenderDestination.PRINT
