"""Hand-written tests for :class:`pypdfbox.debugger.ui.PrintDpiMenu`."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui.print_dpi_menu import PrintDpiMenu


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    PrintDpiMenu._reset_for_testing()
    yield
    PrintDpiMenu._reset_for_testing()


def test_construction_yields_seven_entries(tk_root: tk.Tk) -> None:
    menu = PrintDpiMenu.get_instance(master=tk_root)
    assert menu.get_menu().index("end") == len(PrintDpiMenu.DPIS) - 1
    # Default selection matches upstream: ``0`` ("off").
    assert PrintDpiMenu.get_dpi_selection() == 0


def test_singleton_returns_same_instance(tk_root: tk.Tk) -> None:
    first = PrintDpiMenu.get_instance(master=tk_root)
    second = PrintDpiMenu.get_instance(master=tk_root)
    assert first is second


def test_labels_match_upstream(tk_root: tk.Tk) -> None:
    menu = PrintDpiMenu.get_instance(master=tk_root)
    labels = [menu.get_menu().entrycget(i, "label") for i in range(len(PrintDpiMenu.DPIS))]
    assert labels == ["off", "100 dpi", "200 dpi", "300 dpi", "600 dpi", "1200 dpi", "printer dpi"]


def test_change_dpi_selection_to_each_preset(tk_root: tk.Tk) -> None:
    menu = PrintDpiMenu.get_instance(master=tk_root)
    for dpi in PrintDpiMenu.DPIS:
        menu.change_dpi_selection(dpi)
        assert PrintDpiMenu.get_dpi_selection() == dpi


def test_change_dpi_selection_unknown_value(tk_root: tk.Tk) -> None:
    menu = PrintDpiMenu.get_instance(master=tk_root)
    with pytest.raises(ValueError):
        menu.change_dpi_selection(72)


def test_click_radiobutton_updates_selection(tk_root: tk.Tk) -> None:
    menu = PrintDpiMenu.get_instance(master=tk_root)
    tk_menu = menu.get_menu()
    # Index 3 corresponds to DPIS[3] = 300.
    tk_menu.invoke(3)
    assert PrintDpiMenu.get_dpi_selection() == 300


def test_get_dpi_selection_without_instance_raises() -> None:
    PrintDpiMenu._reset_for_testing()
    with pytest.raises(RuntimeError):
        PrintDpiMenu.get_dpi_selection()
