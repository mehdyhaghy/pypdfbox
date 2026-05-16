"""Hand-written tests for ``TreeViewMenu.create_tree_view_menu``."""

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


def test_create_tree_view_menu_returns_tk_menu_with_three_entries(tk_root: tk.Tk) -> None:
    menu = TreeViewMenu.get_instance(master=tk_root)
    rebuilt = menu.create_tree_view_menu()
    assert isinstance(rebuilt, tk.Menu)
    assert rebuilt.index("end") == 2  # three entries, last index = 2


def test_create_tree_view_menu_entries_match_labels(tk_root: tk.Tk) -> None:
    menu = TreeViewMenu.get_instance(master=tk_root)
    rebuilt = menu.create_tree_view_menu()
    labels = [rebuilt.entrycget(i, "label") for i in range(3)]
    assert labels == [
        TreeViewMenu.VIEW_PAGES,
        TreeViewMenu.VIEW_STRUCTURE,
        TreeViewMenu.VIEW_CROSS_REF_TABLE,
    ]


def test_create_tree_view_menu_private_alias_still_works(tk_root: tk.Tk) -> None:
    menu = TreeViewMenu.get_instance(master=tk_root)
    rebuilt = menu._create_tree_view_menu()  # noqa: SLF001 - back-compat alias
    assert isinstance(rebuilt, tk.Menu)
