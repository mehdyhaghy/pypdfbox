"""Tests covering :class:`StringPane`'s view-construction helpers.

Exercises the promoted upstream-parity methods :meth:`create_hex_view`,
:meth:`create_text_view`, and :meth:`get_text_string`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pypdfbox.cos import COSString
from pypdfbox.debugger.stringpane.string_pane import StringPane


def test_create_text_view_returns_disabled_text_widget(tk_root: tk.Tk) -> None:
    """``create_text_view`` should produce a read-only ``tk.Text``."""
    cos = COSString("payload")
    pane = StringPane(tk_root, cos)
    widget = pane.create_text_view(COSString("another"))
    assert isinstance(widget, tk.Text)
    assert str(widget.cget("state")) == "disabled"
    assert widget.get("1.0", "end-1c") == "another"


def test_create_hex_view_returns_frame_with_byte_content(tk_root: tk.Tk) -> None:
    """``create_hex_view`` returns a ``ttk.Frame`` wrapping ``HexView``."""
    cos = COSString(b"abc")
    pane = StringPane(tk_root, cos)
    frame = pane.create_hex_view(COSString(b"\x10\x20"))
    # ``HexView.get_pane`` returns a ``ttk.Frame`` (or compatible widget).
    assert isinstance(frame, ttk.Frame)
    # The frame should be a child of the StringPane's notebook.
    assert str(frame).startswith(str(pane.get_pane()))


def test_get_text_string_method_matches_module_helper(tk_root: tk.Tk) -> None:
    """The instance method delegates to the module-level helper."""
    cos = COSString("hello")
    pane = StringPane(tk_root, cos)
    assert pane.get_text_string(COSString("hello")) == "hello"
    # Control character forces hex fallback.
    assert pane.get_text_string(COSString(b"\x01\x02")).startswith("<")


def test_private_aliases_resolve_to_public_methods(tk_root: tk.Tk) -> None:
    """Legacy underscore names remain callable as aliases."""
    cos = COSString("x")
    pane = StringPane(tk_root, cos)
    assert StringPane._create_text_view is StringPane.create_text_view
    assert StringPane._create_hex_view is StringPane.create_hex_view
    assert StringPane._get_text_string is StringPane.get_text_string
    # And bound calls produce the same output.
    sample = COSString("ping")
    assert pane._get_text_string(sample) == pane.get_text_string(sample)
