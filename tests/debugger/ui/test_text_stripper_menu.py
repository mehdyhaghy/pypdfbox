"""Hand-written tests for :class:`pypdfbox.debugger.ui.TextStripperMenu`."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui.text_stripper_menu import TextStripperMenu


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    TextStripperMenu._reset_for_testing()
    yield
    TextStripperMenu._reset_for_testing()


def test_construction_yields_two_checkbox_entries(tk_root: tk.Tk) -> None:
    menu = TextStripperMenu.get_instance(master=tk_root)
    assert menu.get_menu().index("end") == 1
    # Defaults: both checkboxes unset.
    assert TextStripperMenu.is_sorted() is False
    assert TextStripperMenu.is_ignore_spaces() is False


def test_singleton_returns_same_instance(tk_root: tk.Tk) -> None:
    first = TextStripperMenu.get_instance(master=tk_root)
    second = TextStripperMenu.get_instance(master=tk_root)
    assert first is second


def test_labels_match_upstream(tk_root: tk.Tk) -> None:
    menu = TextStripperMenu.get_instance(master=tk_root)
    labels = [menu.get_menu().entrycget(i, "label") for i in range(2)]
    assert labels == ["sort", "ignore spaces"]


def test_invoke_sort_toggle(tk_root: tk.Tk) -> None:
    menu = TextStripperMenu.get_instance(master=tk_root)
    tk_menu = menu.get_menu()
    tk_menu.invoke(0)  # "sort"
    assert TextStripperMenu.is_sorted() is True
    assert TextStripperMenu.is_ignore_spaces() is False
    tk_menu.invoke(0)
    assert TextStripperMenu.is_sorted() is False


def test_invoke_ignore_spaces_toggle(tk_root: tk.Tk) -> None:
    menu = TextStripperMenu.get_instance(master=tk_root)
    tk_menu = menu.get_menu()
    tk_menu.invoke(1)  # "ignore spaces"
    assert TextStripperMenu.is_ignore_spaces() is True
    assert TextStripperMenu.is_sorted() is False


def test_state_without_instance() -> None:
    TextStripperMenu._reset_for_testing()
    # Before the singleton is built we report unselected for both toggles
    # rather than crashing — useful for hosts that probe state defensively.
    assert TextStripperMenu.is_sorted() is False
    assert TextStripperMenu.is_ignore_spaces() is False
