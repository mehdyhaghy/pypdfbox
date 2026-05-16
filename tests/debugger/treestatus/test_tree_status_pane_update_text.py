"""Hand-written tests for ``TreeStatusPane.update_text`` (upstream parity)."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.debugger.treestatus import TreeStatus, TreeStatusPane


@pytest.fixture
def _tk_root() -> tk.Tk:
    if os.environ.get("PYPDFBOX_SKIP_TK") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1")
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless guard
        pytest.skip(f"Tk display unavailable: {exc}")
    try:
        yield root
    finally:
        root.destroy()


def test_update_text_sets_status_var(_tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(_tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    pane.update_text("Root/Foo")
    assert pane._status_var.get() == "Root/Foo"  # noqa: SLF001


def test_update_text_with_none_clears_field(_tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(_tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    pane._status_var.set("stale")  # noqa: SLF001
    pane.update_text(None)
    # ``None`` becomes the empty string, mirroring Swing's setText(null).
    assert pane._status_var.get() == ""


def test_update_text_resets_style_to_default(_tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(_tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    pane._status_field.configure(style=pane._error_style)  # noqa: SLF001
    pane.update_text("clean")
    assert pane._status_field.cget("style") == pane._default_style  # noqa: SLF001


def test_update_text_before_init_is_noop(_tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(_tk_root)
    pane = TreeStatusPane(tree)
    # No init() — _status_var is None; method early-returns.
    pane.update_text("anything")  # no exception


def test_private_alias_still_works(_tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(_tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    pane._update_text("via alias")  # noqa: SLF001 - back-compat alias
    assert pane._status_var.get() == "via alias"  # noqa: SLF001


def test_value_changed_routes_through_update_text(_tk_root: tk.Tk) -> None:
    """``value_changed`` should call the now-public ``update_text`` helper."""
    tree = ttk.Treeview(_tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    pane.update_tree_status(TreeStatus(COSDictionary()))
    pane.value_changed((COSDictionary(),))
    # Empty-path → empty string — the update_text branch was taken.
    assert pane._status_var.get() == ""  # noqa: SLF001
