"""Hand-written tests for :class:`pypdfbox.debugger.ui.TreeViewMenu`."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    TreeViewMenu._reset_for_testing()
    yield
    TreeViewMenu._reset_for_testing()


def test_construction_yields_three_entries(tk_root: tk.Tk) -> None:
    menu = TreeViewMenu.get_instance(master=tk_root)
    assert menu.get_menu().index("end") == 2
    # Default selection mirrors upstream (VIEW_PAGES on a fresh instance).
    assert menu.get_tree_view_selection() == TreeViewMenu.VIEW_PAGES


def test_singleton_returns_same_instance(tk_root: tk.Tk) -> None:
    first = TreeViewMenu.get_instance(master=tk_root)
    second = TreeViewMenu.get_instance(master=tk_root)
    assert first is second


def test_labels_match_upstream(tk_root: tk.Tk) -> None:
    menu = TreeViewMenu.get_instance(master=tk_root)
    labels = [menu.get_menu().entrycget(i, "label") for i in range(3)]
    assert labels == [
        TreeViewMenu.VIEW_PAGES,
        TreeViewMenu.VIEW_STRUCTURE,
        TreeViewMenu.VIEW_CROSS_REF_TABLE,
    ]


def test_set_tree_view_selection_to_each_view(tk_root: tk.Tk) -> None:
    menu = TreeViewMenu.get_instance(master=tk_root)
    for label in (
        TreeViewMenu.VIEW_PAGES,
        TreeViewMenu.VIEW_STRUCTURE,
        TreeViewMenu.VIEW_CROSS_REF_TABLE,
    ):
        menu.set_tree_view_selection(label)
        assert menu.get_tree_view_selection() == label


def test_set_tree_view_selection_invalid(tk_root: tk.Tk) -> None:
    menu = TreeViewMenu.get_instance(master=tk_root)
    with pytest.raises(ValueError):
        menu.set_tree_view_selection("Mystery view")


def test_is_valid_view_mode() -> None:
    assert TreeViewMenu.is_valid_view_mode(TreeViewMenu.VIEW_PAGES)
    assert TreeViewMenu.is_valid_view_mode(TreeViewMenu.VIEW_STRUCTURE)
    assert TreeViewMenu.is_valid_view_mode(TreeViewMenu.VIEW_CROSS_REF_TABLE)
    assert not TreeViewMenu.is_valid_view_mode("Other")
    assert not TreeViewMenu.is_valid_view_mode("")


def test_click_radiobutton_updates_selection(tk_root: tk.Tk) -> None:
    menu = TreeViewMenu.get_instance(master=tk_root)
    tk_menu = menu.get_menu()
    tk_menu.invoke(1)
    assert menu.get_tree_view_selection() == TreeViewMenu.VIEW_STRUCTURE
