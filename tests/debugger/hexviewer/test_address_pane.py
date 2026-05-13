"""Widget tests for ``AddressPane``."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.hexviewer.address_pane import AddressPane


def test_renders_addresses_for_each_line(tk_root: tk.Tk) -> None:
    pane = AddressPane(tk_root, total=3)
    text = pane.get("1.0", "end-1c")
    lines = text.splitlines()
    assert lines == ["00000000", "00000010", "00000020"]


def test_set_selected_highlights_row(tk_root: tk.Tk) -> None:
    pane = AddressPane(tk_root, total=3)
    pane.set_selected(17)  # row 2 (offset 0x10 -> 0x11 displayed)
    text = pane.get("1.0", "end-1c")
    lines = text.splitlines()
    assert lines[1] == "00000011"
    # The "selected" tag should cover that row.
    ranges = pane.tag_ranges("selected")
    assert ranges  # non-empty
