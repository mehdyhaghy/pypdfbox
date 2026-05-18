"""Wave 1349 coverage-boost tests for :class:`TreeStatusPane`.

Targets the success branch of ``_on_text_input`` (lines 128-130) where
``_locate_item_for_path`` returns a real tree item: the pane must
``selection_set`` / ``see`` / ``focus_set`` the located node.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
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


def test_text_input_with_locatable_path_selects_and_focuses_item(tk_root: tk.Tk) -> None:
    """When ``_locate_item_for_path`` resolves the path to an item, the
    pane must call ``selection_set`` / ``see`` / ``focus_set`` on the
    tree (lines 128-130)."""
    tree = ttk.Treeview(tk_root)

    class _Pane(TreeStatusPane):
        def _locate_item_for_path(self, path: object) -> str:
            # Resolve every path to the same fixed item id.
            return "iid_target"

    pane = _Pane(tree)
    pane.init()

    # Build a tree carrying the target id.
    tree.insert("", "end", iid="iid_target", text="target row")

    root_dict = COSDictionary()
    root_dict.set_item(COSName.get_pdf_name("Foo"), COSInteger.get(1))
    pane.update_tree_status(TreeStatus(root_dict))

    # Type a path that resolves successfully; the override returns the
    # synthetic item id.
    pane._status_var.set("Foo")  # type: ignore[attr-defined]  # noqa: SLF001
    pane._on_text_input(None)  # type: ignore[arg-type]  # noqa: SLF001

    # selection_set + focus_set ran → tree state reflects the change.
    assert tree.selection() == ("iid_target",)
    # focus_set is a no-op assertion target (Tk records focus on a widget,
    # not on a specific item); we assert that the call did not raise.
