"""Tkinter port of ``org.apache.pdfbox.debugger.stringpane.StringPane``.

The Swing original lays out a ``JTabbedPane`` with a "Text View" tab
(``JTextPane``) and a "Hex view" tab embedding the hex viewer. The
pure-data text-extraction helper :func:`get_text_string` mirrors
upstream's ``getTextString`` private — when the decoded text contains
unprintable ISO control characters (other than ``\\n``, ``\\r``,
``\\t``), the renderer falls back to a hexified ``<...>`` form.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk

from pypdfbox.cos import COSString
from pypdfbox.debugger.hexviewer.hex_view import HexView


def get_text_string(cos_string: COSString) -> str:
    """Return the user-facing decoded representation of ``cos_string``.

    Mirrors upstream ``StringPane.getTextString``: if the decoded text
    contains any control character other than ``\\n``, ``\\r``, ``\\t``,
    the entire string is rendered as a hex literal.
    """
    text = cos_string.get_string()
    for char in text:
        if _is_iso_control(char) and char not in ("\n", "\r", "\t"):
            return "<" + cos_string.to_hex_string() + ">"
    return text


def _is_iso_control(char: str) -> bool:
    """Mirror ``Character.isISOControl(int)`` for a single-char string."""
    code = ord(char)
    return code <= 0x1F or 0x7F <= code <= 0x9F


class StringPane:
    """Tabbed view onto a ``COSString``: text + hex."""

    _TEXT_TAB = "Text View"
    _HEX_TAB = "Hex view"
    DEFAULT_WIDTH = 300
    DEFAULT_HEIGHT = 500

    def __init__(self, master: tk.Misc | None, cos_string: COSString) -> None:
        self._cos_string = cos_string
        self._tabbed_pane = ttk.Notebook(master)
        with contextlib.suppress(tk.TclError):
            self._tabbed_pane.configure(
                width=self.DEFAULT_WIDTH, height=self.DEFAULT_HEIGHT
            )

        text_widget = self._create_text_view(cos_string)
        hex_widget = self._create_hex_view(cos_string)
        self._tabbed_pane.add(text_widget, text=self._TEXT_TAB)
        self._tabbed_pane.add(hex_widget, text=self._HEX_TAB)

        self._text_widget = text_widget
        self._hex_view = hex_widget

    # ---- public accessors --------------------------------------------------

    def get_pane(self) -> ttk.Notebook:
        """Return the underlying ``ttk.Notebook`` (upstream returns the JTabbedPane)."""
        return self._tabbed_pane

    @property
    def text(self) -> tk.Text:
        """The underlying ``tk.Text`` for the "Text View" tab."""
        return self._text_widget

    # ---- internals ---------------------------------------------------------

    def _create_text_view(self, cos_string: COSString) -> tk.Text:
        text = tk.Text(self._tabbed_pane, wrap="word")
        text.insert("1.0", get_text_string(cos_string))
        text.configure(state="disabled")
        return text

    def _create_hex_view(self, cos_string: COSString) -> ttk.Frame:
        hex_view = HexView(self._tabbed_pane, cos_string.get_bytes())
        return hex_view.get_pane()
