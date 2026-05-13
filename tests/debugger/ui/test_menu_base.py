"""Hand-written tests for :class:`pypdfbox.debugger.ui.MenuBase`."""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.ui.menu_base import MenuBase


def test_get_menu_without_set_raises() -> None:
    base = MenuBase()
    with pytest.raises(RuntimeError):
        base.get_menu()


def test_set_and_get_menu(tk_root: tk.Tk) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    assert base.get_menu() is menu


def test_add_menu_appends_command(tk_root: tk.Tk) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    calls: list[str] = []
    base.add_menu("Open", lambda: calls.append("open"))
    base.add_menu("Save", lambda: calls.append("save"))
    assert menu.index("end") == 1  # zero-based, two entries
    menu.invoke(0)
    menu.invoke(1)
    assert calls == ["open", "save"]


def test_add_radio_group_round_trip(tk_root: tk.Tk) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    observed: list[str] = []
    var = base.add_radio_group(
        ["A", "B", "C"], current="B", on_change=observed.append
    )
    assert var.get() == "B"
    # Simulate clicking the third entry.
    menu.invoke(2)
    assert var.get() == "C"
    assert observed == ["C"]


def test_add_radio_group_defaults_to_first(tk_root: tk.Tk) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    var = base.add_radio_group(["X", "Y"], current=None, on_change=None)
    assert var.get() == "X"


def test_set_enable_menu_disables_entries(tk_root: tk.Tk) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    base.add_menu("A", None)
    base.add_menu("B", None)
    base.set_enable_menu(False)
    assert menu.entrycget(0, "state") == "disabled"
    base.set_enable_menu(True)
    assert menu.entrycget(0, "state") == "normal"


def test_add_menu_listeners_replaces_commands(tk_root: tk.Tk) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    # Initially the entries have their own commands.
    fired: list[str] = []
    base.add_menu("First", lambda: fired.append("orig-first"))
    base.add_menu("Second", lambda: fired.append("orig-second"))
    # Replace with a single uniform listener.
    received: list[str] = []
    base.add_menu_listeners(received.append)
    menu.invoke(0)
    menu.invoke(1)
    assert received == ["First", "Second"]
    # Original callbacks should not fire after replacement.
    assert fired == []
