"""Widget tests for ``ASCIIPane``."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.hexviewer.ascii_pane import ASCIIPane
from pypdfbox.debugger.hexviewer.hex_model import HexModel


def test_renders_printable_ascii(tk_root: tk.Tk) -> None:
    model = HexModel(b"Hello\x00World")
    pane = ASCIIPane(tk_root, model)
    text = pane.get("1.0", "end-1c")
    assert text.startswith("Hello.World")


def test_set_selected_highlights_byte(tk_root: tk.Tk) -> None:
    model = HexModel(b"Hello\x00World")
    pane = ASCIIPane(tk_root, model)
    pane.set_selected(0)
    ranges = pane.tag_ranges("selected")
    assert ranges
