"""Hand-written tests for :class:`TreeStatusPane`.

The pane needs a live Tk root, so each test skips itself when a display is
not available (e.g. headless CI without Xvfb).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.debugger.treestatus import TreeStatus, TreeStatusPane


@pytest.fixture
def tk_root() -> tk.Tk:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless guard
        pytest.skip(f"Tk display unavailable: {exc}")
    try:
        yield root
    finally:
        root.destroy()


def test_pane_constructs_and_exposes_panel(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    panel = pane.get_panel()
    assert isinstance(panel, ttk.Frame)


def test_pane_get_panel_before_init_raises(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    with pytest.raises(RuntimeError):
        pane.get_panel()


def test_update_tree_status_enables_field(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    root_dict = COSDictionary()
    pane.update_tree_status(TreeStatus(root_dict))
    # Field becomes editable; we read state via the underlying widget.
    state = pane._status_field.cget("state")  # type: ignore[attr-defined]
    assert str(state) == "normal"


def test_value_changed_updates_text(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    pane.update_tree_status(TreeStatus(COSDictionary()))
    # An empty single-node path produces an empty status string.
    pane.value_changed((COSDictionary(),))
    assert pane._status_var.get() == ""  # type: ignore[attr-defined]
