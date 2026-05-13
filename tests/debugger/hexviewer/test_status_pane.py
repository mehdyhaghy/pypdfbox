"""Widget tests for ``StatusPane``."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.hexviewer.status_pane import StatusPane


def test_initial_state_empty(tk_root: tk.Tk) -> None:
    pane = StatusPane(tk_root)
    assert pane.get_line_text() == ""
    assert pane.get_column_text() == ""
    assert pane.get_index_text() == ""


def test_update_status_sets_labels(tk_root: tk.Tk) -> None:
    pane = StatusPane(tk_root)
    pane.update_status(17)  # line 2, col 2, index 17
    assert pane.get_line_text() == "2"
    assert pane.get_column_text() == "2"
    assert pane.get_index_text() == "17"
