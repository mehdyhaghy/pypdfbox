"""Widget tests for ``HexView``."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pypdfbox.debugger.hexviewer.hex_view import HexView


def test_constructs_without_data(tk_root: tk.Tk) -> None:
    view = HexView(tk_root)
    assert isinstance(view.get_pane(), ttk.Frame)
    assert view.get_editor() is None


def test_constructs_with_bytes(tk_root: tk.Tk) -> None:
    view = HexView(tk_root, b"hello")
    assert view.get_editor() is not None


def test_change_data_replaces_editor(tk_root: tk.Tk) -> None:
    view = HexView(tk_root, b"a")
    first_editor = view.get_editor()
    view.change_data(b"changed data")
    second_editor = view.get_editor()
    assert second_editor is not None
    assert second_editor is not first_editor


def test_geometry_constants_match_upstream() -> None:
    assert HexView.HEX_PANE_WIDTH == 600
    assert HexView.ADDRESS_PANE_WIDTH == 120
    assert HexView.ASCII_PANE_WIDTH == 270
    assert HexView.TOTAL_WIDTH == 990
    assert HexView.CHAR_HEIGHT == 20
    assert HexView.CHAR_WIDTH == 35
    assert HexView.LINE_INSET == 20
