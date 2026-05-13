"""Column-header banner for the hex viewer.

Tkinter port of ``org.apache.pdfbox.debugger.hexviewer.UpperPane``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


class UpperPane(ttk.Frame):
    """Static header showing ``Offset`` / hex column indices / ``Text``."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, borderwidth=1, relief="solid")
        self._font = tkfont.Font(family="Courier", size=11)
        self._build()

    def _build(self) -> None:
        offset_label = ttk.Label(self, text="Offset", font=self._font)
        offset_label.grid(row=0, column=0, padx=(8, 8), sticky="w")

        cols = " ".join(f"{i:02X}" for i in range(16))
        ttk.Label(self, text=cols, font=self._font).grid(
            row=0, column=1, padx=(0, 16), sticky="w"
        )

        ttk.Label(self, text="Text", font=self._font).grid(
            row=0, column=2, sticky="w"
        )
