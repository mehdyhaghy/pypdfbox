"""Widget tests for ``UpperPane``."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.hexviewer.upper_pane import UpperPane


def test_upper_pane_constructs(tk_root: tk.Tk) -> None:
    pane = UpperPane(tk_root)
    # Three labels: Offset, hex columns, Text.
    children = pane.winfo_children()
    assert len(children) == 3
    texts = [c.cget("text") for c in children]
    assert texts[0] == "Offset"
    assert texts[2] == "Text"
    # The column-header text should contain "00 01 ... 0F".
    assert "00" in texts[1] and "0F" in texts[1]
