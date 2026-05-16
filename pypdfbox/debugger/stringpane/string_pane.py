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

        text_widget = self.create_text_view(cos_string)
        hex_widget = self.create_hex_view(cos_string)
        self._tabbed_pane.add(text_widget, text=self._TEXT_TAB)
        self._tabbed_pane.add(hex_widget, text=self._HEX_TAB)

        self._text_widget = text_widget

    # ---- public accessors --------------------------------------------------

    def get_pane(self) -> ttk.Notebook:
        """Return the underlying ``ttk.Notebook`` (upstream returns the JTabbedPane)."""
        return self._tabbed_pane

    @property
    def text(self) -> tk.Text:
        """The underlying ``tk.Text`` for the "Text View" tab."""
        return self._text_widget

    # ---- view construction (upstream parity) ------------------------------

    def create_text_view(self, cos_string: COSString) -> tk.Text:
        """Build the "Text View" widget for ``cos_string``.

        Port of upstream's private ``createTextView``. Produces a
        read-only ``tk.Text`` widget whose content is the decoded text
        (or a hex literal when control characters are present).
        """
        text = tk.Text(self._tabbed_pane, wrap="word")
        text.insert("1.0", self.get_text_string(cos_string))
        text.configure(state="disabled")
        return text

    def create_hex_view(self, cos_string: COSString) -> ttk.Frame:
        """Build the "Hex view" widget for ``cos_string``.

        Port of upstream's private ``createHexView``. Wraps a
        :class:`HexView` over the raw bytes and returns its outer pane.
        """
        hex_view = HexView(self._tabbed_pane, cos_string.get_bytes())
        return hex_view.get_pane()

    def get_text_string(self, cos_string: COSString) -> str:
        """Return the decoded text representation of ``cos_string``.

        Port of upstream's private ``getTextString`` (instance method).
        Delegates to the module-level :func:`get_text_string` helper.
        """
        return get_text_string(cos_string)

    # ---- private aliases (for in-tree call sites that still expect them) --

    _create_text_view = create_text_view
    _create_hex_view = create_hex_view
    _get_text_string = get_text_string
