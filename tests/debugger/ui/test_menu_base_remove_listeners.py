"""Hand-written tests for ``MenuBase.remove_action_listeners``."""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.ui.menu_base import MenuBase


def test_remove_action_listeners_clears_command(tk_root: tk.Tk) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    fired: list[str] = []
    base.add_menu("Open", lambda: fired.append("open"))
    base.remove_action_listeners(0)
    # Invoking the entry now does nothing — command is the empty string.
    menu.invoke(0)
    assert fired == []


def test_remove_action_listeners_without_menu_is_noop() -> None:
    # No bound menu → silent return, no exception.
    base = MenuBase()
    base.remove_action_listeners(0)


def test_remove_action_listeners_bad_index_swallowed(tk_root: tk.Tk) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    base.add_menu("Only", lambda: None)
    # Out-of-range index does not raise.
    base.remove_action_listeners(99)


def test_add_menu_listeners_calls_remove_first(tk_root: tk.Tk) -> None:
    """``add_menu_listeners`` must clear pre-existing commands first.

    Mirrors upstream's per-item ``removeActionListeners`` loop body — the
    new listener should be the *only* one that fires after re-binding.
    """
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    fired_orig: list[str] = []
    fired_new: list[str] = []
    base.add_menu("A", lambda: fired_orig.append("orig"))
    base.add_menu_listeners(fired_new.append)
    menu.invoke(0)
    assert fired_orig == []
    assert fired_new == ["A"]


def test_remove_action_listeners_alias_still_works(tk_root: tk.Tk) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    fired: list[str] = []
    base.add_menu("Foo", lambda: fired.append("foo"))
    base._remove_action_listeners(0)  # noqa: SLF001 - back-compat alias
    menu.invoke(0)
    assert fired == []


@pytest.mark.parametrize("count", [1, 2, 3])
def test_remove_action_listeners_per_index(tk_root: tk.Tk, count: int) -> None:
    base = MenuBase()
    menu = tk.Menu(tk_root, tearoff=0)
    base.set_menu(menu)
    fired: list[int] = []
    for i in range(count):
        base.add_menu(f"E{i}", lambda i=i: fired.append(i))
    # Detach entry 0 only.
    base.remove_action_listeners(0)
    for i in range(count):
        menu.invoke(i)
    assert 0 not in fired
    if count > 1:
        assert all(i in fired for i in range(1, count))
