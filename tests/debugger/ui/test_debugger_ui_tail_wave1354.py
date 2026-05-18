"""Wave 1354 tail-sweep for the debugger UI helpers.

Covers:

* ``LogDialog.set_visible(True)`` first-time path that builds the
  toplevel via :meth:`show` (line 92 in ``log_dialog.py``).
* ``TreeViewMenu.get_tree_view_selection`` raise path when the
  Tk ``StringVar`` is set to an out-of-band label (line 90 in
  ``tree_view_menu.py``).
* ``XrefEntries.index_of`` fallback that returns 0 when the supplied
  entry's key is absent (line 49 in ``xref_entries.py``).
* ``Searcher.search`` no-panel branch with zero matches (lines 140-141
  in ``textsearcher/searcher.py``).
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk

import pytest

from pypdfbox.cos import COSObjectKey
from pypdfbox.debugger.ui import XrefEntries, XrefEntry
from pypdfbox.debugger.ui.log_dialog import LogDialog
from pypdfbox.debugger.ui.textsearcher.searcher import Searcher
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.pdmodel import PDDocument


def test_log_dialog_set_visible_true_first_call_builds_toplevel(
    tk_root: tk.Tk,
) -> None:
    dialog = LogDialog(tk_root)
    dialog.set_visible(True)
    try:
        # set_visible(True) routes to show() which builds the toplevel.
        assert dialog._toplevel is not None  # type: ignore[attr-defined]
        assert dialog._toplevel.winfo_exists()  # type: ignore[attr-defined]
    finally:
        with contextlib.suppress(tk.TclError):
            dialog._toplevel.destroy()  # type: ignore[attr-defined]


def test_tree_view_menu_get_selection_raises_for_unknown_label(
    tk_root: tk.Tk,
) -> None:
    TreeViewMenu._reset_for_testing()
    menu = TreeViewMenu(tk_root)
    # Force the underlying StringVar into an invalid state.
    menu._var.set("bogus-label")  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="No tree view selection"):
        menu.get_tree_view_selection()
    TreeViewMenu._reset_for_testing()


def test_xref_entries_index_of_returns_zero_for_unknown_key() -> None:
    doc = PDDocument()
    try:
        doc.get_document().add_xref_table({COSObjectKey(7, 0): 70})
        entries = XrefEntries(doc)
        stranger = XrefEntry(0, COSObjectKey(99, 0), 999, None)
        assert entries.index_of(stranger) == 0
    finally:
        doc.close()


def test_searcher_no_panel_search_with_zero_matches(tk_root: tk.Tk) -> None:
    text = tk.Text(ttk.Frame(tk_root))
    text.insert("1.0", "hello world")
    searcher = Searcher(text)
    # No init() — the panel is None so search() takes the direct-engine path.
    highlights = searcher.search("zzz-no-match-zzz")
    assert highlights == []
    assert searcher._total_match == 0  # type: ignore[attr-defined]
    assert searcher._current_match == -1  # type: ignore[attr-defined]
