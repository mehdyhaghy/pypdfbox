"""Bottom status panel of the debugger window.

Ported from ``org.apache.pdfbox.debugger.ui.ReaderBottomPanel``.

The Swing original is a ``JPanel`` with a status label on the left and a
clickable "log" label on the right that opens :class:`LogDialog`. We port the
same structure using ``ttk.Frame`` + ``ttk.Label``; the log label is wired
with a left-mouse-button binding to call ``LogDialog.instance().show()``.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk
from typing import Any


class ReaderBottomPanel(ttk.Frame):
    """A panel to display at the bottom of the window for status and other stuff."""

    def __init__(self, master: tk.Misc | None = None, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self._status_label: ttk.Label | None = None
        self._log_label: ttk.Label | None = None

    # --- two-step construction (Swing parity) ----------------------------

    def init(self) -> None:
        """Build the labels. Mirrors upstream's ``init()``."""
        self.configure(padding=(5, 0, 5, 0))
        self._status_label = ttk.Label(self, text="Ready")
        self._status_label.pack(side="left", anchor="w")
        self._log_label = ttk.Label(self, text="", cursor="hand2")
        self._log_label.pack(side="right", anchor="e")
        # Wire the click handler. Imported lazily to avoid a circular import.
        self._log_label.bind("<Button-1>", self._on_log_clicked)

    # --- accessors --------------------------------------------------------

    def get_status_label(self) -> ttk.Label | None:
        return self._status_label

    def get_log_label(self) -> ttk.Label | None:
        return self._log_label

    # --- internal ---------------------------------------------------------

    def _on_log_clicked(self, _event: tk.Event) -> None:  # pragma: no cover - GUI
        # Imported lazily so this module loads cleanly when LogDialog hasn't
        # been built yet (e.g. during early debugger start-up).
        from .log_dialog import LogDialog

        dialog = LogDialog.instance()
        if dialog is None:
            return
        toplevel = dialog.show()
        with contextlib.suppress(tk.TclError):
            toplevel.geometry("800x400")
