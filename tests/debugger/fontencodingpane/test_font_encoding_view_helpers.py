"""Tests covering :class:`FontEncodingView`'s view-construction helpers.

Exercises the promoted upstream-parity methods :meth:`create_view`,
:meth:`get_header_panel`, and :meth:`get_table`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pypdfbox.debugger.fontencodingpane.font_encoding_view import (
    FontEncodingView,
)


def test_create_view_builds_header_and_table(tk_root: tk.Tk) -> None:
    """``create_view`` populates ``_header_frame`` and ``_tree``."""
    view = FontEncodingView(
        tk_root,
        [[1, "A", "A", "No glyph"]],
        {"Font": "Helvetica"},
        ["Code", "Glyph Name", "Unicode", "Glyph"],
        None,
    )
    # ``__init__`` already calls ``create_view``; the side effects must be
    # observable.
    assert view._header_frame is not None
    assert view._tree is not None
    assert len(view._tree.get_children()) == 1


def test_get_header_panel_returns_frame_with_labels(tk_root: tk.Tk) -> None:
    """A non-empty attribute map yields a frame with one label per entry."""
    view = FontEncodingView(
        tk_root,
        [],
        None,
        ["Code", "Glyph"],
        None,
    )
    frame = view.get_header_panel({"Font": "Helvetica", "Encoding": "WinAnsi"})
    assert isinstance(frame, ttk.Frame)
    # Two attributes → two grid children.
    assert len(frame.grid_slaves()) == 2


def test_get_header_panel_returns_none_when_empty(tk_root: tk.Tk) -> None:
    """Empty / ``None`` attribute maps must yield ``None``, not an empty frame."""
    view = FontEncodingView(
        tk_root,
        [],
        None,
        ["Code", "Glyph"],
        None,
    )
    assert view.get_header_panel(None) is None
    assert view.get_header_panel({}) is None


def test_get_table_returns_treeview_with_configured_columns(
    tk_root: tk.Tk,
) -> None:
    """``get_table`` returns a fresh ``ttk.Treeview`` with rows populated."""
    rows = [
        [65, "A", "A", "No glyph"],
        [66, "B", "B", "No glyph"],
    ]
    view = FontEncodingView(
        tk_root,
        rows,
        None,
        ["Code", "Glyph Name", "Unicode", "Glyph"],
        None,
    )
    tree = view.get_table()
    assert isinstance(tree, ttk.Treeview)
    assert len(tree.get_children()) == 2
    # ``#0`` column header should be the first declared column name.
    assert tree.heading("#0")["text"] == "Code"
