"""Bottom status bar for the hex viewer.

Tkinter port of ``org.apache.pdfbox.debugger.hexviewer.StatusPane``. Shows
``Line / Column / Index`` for the currently selected byte.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pypdfbox.debugger.hexviewer.hex_model import HexModel


class StatusPane(ttk.Frame):
    """Status line displaying line, column and absolute byte index."""

    _HEIGHT = 20

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, height=self._HEIGHT)
        self._line_var = tk.StringVar(master=self, value="")
        self._col_var = tk.StringVar(master=self, value="")
        self._index_var = tk.StringVar(master=self, value="")
        self.create_view()

    def create_view(self) -> None:
        """Build the line / column / index label row.

        Mirrors upstream private ``StatusPane.createView()``. Public on
        the Python port for parity tooling.
        """
        ttk.Label(self, text="Line:").grid(row=0, column=0, padx=(4, 2))
        ttk.Label(self, textvariable=self._line_var, width=10).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Label(self, text="Column:").grid(row=0, column=2, padx=(0, 2))
        ttk.Label(self, textvariable=self._col_var, width=10).grid(
            row=0, column=3, padx=(0, 8)
        )
        ttk.Label(self, text="Index:").grid(row=0, column=4, padx=(0, 2))
        ttk.Label(self, textvariable=self._index_var, width=12).grid(
            row=0, column=5, padx=(0, 4)
        )

    # Back-compat private alias.
    _create_view = create_view

    def update_status(self, index: int) -> None:
        self._line_var.set(str(HexModel.line_number(index)))
        self._col_var.set(str(HexModel.element_index_in_line(index) + 1))
        self._index_var.set(str(index))

    # Test/inspection helpers --------------------------------------------

    def get_line_text(self) -> str:
        return self._line_var.get()

    def get_column_text(self) -> str:
        return self._col_var.get()

    def get_index_text(self) -> str:
        return self._index_var.get()
