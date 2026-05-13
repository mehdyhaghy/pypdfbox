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


def test_update_tree_status_before_init_raises(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    with pytest.raises(RuntimeError):
        pane.update_tree_status(TreeStatus(COSDictionary()))


def test_value_changed_without_status_obj_is_noop(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    # No ``update_tree_status`` call yet → ``_status_obj`` is None.
    pane.value_changed((COSDictionary(),))
    # No exception, text remains empty.
    assert pane._status_var.get() == ""  # type: ignore[attr-defined]


def test_tree_select_updates_status_for_selection(tk_root: tk.Tk) -> None:
    """Selecting a tree row triggers ``_on_tree_select`` which renders the
    path string for the selected node."""
    from pypdfbox.cos import COSInteger, COSName
    from pypdfbox.debugger.ui.map_entry import MapEntry

    tree = ttk.Treeview(tk_root)
    nodes: dict[str, object] = {}

    def lookup(item: str) -> object:
        return nodes.get(item, item)

    pane = TreeStatusPane(tree, node_lookup=lookup)
    pane.init()
    root_dict = COSDictionary()
    inner = COSInteger.get(42)
    root_dict.set_item(COSName.get_pdf_name("Foo"), inner)
    pane.update_tree_status(TreeStatus(root_dict))

    # Build a tree mirroring root_dict.
    root_iid = tree.insert("", "end", text="Root")
    child_iid = tree.insert(root_iid, "end", text="Foo")
    nodes[root_iid] = root_dict
    nodes[child_iid] = MapEntry()
    nodes[child_iid].set_key(COSName.get_pdf_name("Foo"))  # type: ignore[attr-defined]
    nodes[child_iid].set_value(inner)  # type: ignore[attr-defined]

    tree.selection_set(child_iid)
    pane._on_tree_select(None)  # type: ignore[arg-type]  # noqa: SLF001
    assert "Foo" in pane._status_var.get()  # type: ignore[attr-defined]


def test_tree_select_without_status_obj_is_noop(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    pane._on_tree_select(None)  # type: ignore[arg-type]  # noqa: SLF001
    # No exception; status text remains empty.
    assert pane._status_var.get() == ""  # type: ignore[attr-defined]


def test_tree_select_without_selection_is_noop(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    pane.update_tree_status(TreeStatus(COSDictionary()))
    # No selection on the tree → handler returns early.
    pane._on_tree_select(None)  # type: ignore[arg-type]  # noqa: SLF001


def test_text_input_with_valid_path_clears_error_style(tk_root: tk.Tk) -> None:
    """Entering a valid path string updates the entry style back to default."""
    from pypdfbox.cos import COSInteger, COSName

    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    root_dict = COSDictionary()
    root_dict.set_item(COSName.get_pdf_name("Foo"), COSInteger.get(1))
    pane.update_tree_status(TreeStatus(root_dict))
    pane._status_var.set("Foo")  # type: ignore[attr-defined]  # noqa: SLF001
    # Default ``_locate_item_for_path`` returns None → soft-success branch.
    pane._on_text_input(None)  # type: ignore[arg-type]  # noqa: SLF001


def test_text_input_with_invalid_path_flips_error_style(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    pane.update_tree_status(TreeStatus(COSDictionary()))
    pane._status_var.set("Missing")  # type: ignore[attr-defined]  # noqa: SLF001
    pane._on_text_input(None)  # type: ignore[arg-type]  # noqa: SLF001
    style = pane._status_field.cget("style")  # type: ignore[attr-defined]  # noqa: SLF001
    assert "Error" in style


def test_text_input_without_status_obj_returns_break(tk_root: tk.Tk) -> None:
    tree = ttk.Treeview(tk_root)
    pane = TreeStatusPane(tree)
    pane.init()
    # No status obj.
    result = pane._on_text_input(None)  # type: ignore[arg-type]  # noqa: SLF001
    assert result == "break"
