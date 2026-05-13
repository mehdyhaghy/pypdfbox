"""Hand-written tests for ``pypdfbox.debugger.ui.ReaderBottomPanel``."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.ui import ReaderBottomPanel


def test_init_creates_status_and_log_labels(tk_root: tk.Tk) -> None:
    panel = ReaderBottomPanel(tk_root)
    assert panel.get_status_label() is None
    assert panel.get_log_label() is None
    panel.init()
    status = panel.get_status_label()
    log_label = panel.get_log_label()
    assert status is not None
    assert log_label is not None
    assert status.cget("text") == "Ready"
    assert log_label.cget("text") == ""


def test_log_label_has_hand_cursor(tk_root: tk.Tk) -> None:
    panel = ReaderBottomPanel(tk_root)
    panel.init()
    log_label = panel.get_log_label()
    assert log_label is not None
    assert str(log_label.cget("cursor")) == "hand2"


def test_log_label_bound_to_left_click(tk_root: tk.Tk) -> None:
    panel = ReaderBottomPanel(tk_root)
    panel.init()
    log_label = panel.get_log_label()
    assert log_label is not None
    # ``bind`` returns the bound script when no func is supplied. A non-empty
    # binding means we wired a click handler.
    bound = log_label.bind("<Button-1>")
    assert bound != ""
