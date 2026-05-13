"""Top-level entry point for the hex viewer subsystem.

Tkinter port of ``org.apache.pdfbox.debugger.hexviewer.HexView``. The
upstream class exposes a ``JComponent``; here we expose a ``ttk.Frame``
which can be packed into any Tkinter container.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pypdfbox.debugger.hexviewer.hex_editor import HexEditor
from pypdfbox.debugger.hexviewer.hex_model import HexModel


class HexView:
    """High-level wrapper around ``HexEditor`` that owns a Tk frame."""

    # Mirrored geometry constants from upstream HexView.
    FONT_SIZE = 11
    CHAR_HEIGHT = 20
    CHAR_WIDTH = 35
    LINE_INSET = 20
    HEX_PANE_WIDTH = 600
    ADDRESS_PANE_WIDTH = 120
    ASCII_PANE_WIDTH = 270
    TOTAL_WIDTH = HEX_PANE_WIDTH + ADDRESS_PANE_WIDTH + ASCII_PANE_WIDTH

    def __init__(
        self,
        master: tk.Misc,
        bytes_: bytes | bytearray | None = None,
    ) -> None:
        self._main_pane = ttk.Frame(master)
        self._editor: HexEditor | None = None
        if bytes_ is not None:
            self._editor = HexEditor(self._main_pane, HexModel(bytes_))
            self._editor.pack(fill="both", expand=True)

    def change_data(self, bytes_: bytes | bytearray) -> None:
        """Replace the currently displayed data with *bytes_*."""

        for child in self._main_pane.winfo_children():
            child.destroy()
        model = HexModel(bytes_)
        self._editor = HexEditor(self._main_pane, model)
        self._editor.pack(fill="both", expand=True)

    def get_pane(self) -> ttk.Frame:
        return self._main_pane

    # ------------------------------------------------------------- testing

    def get_editor(self) -> HexEditor | None:
        return self._editor
