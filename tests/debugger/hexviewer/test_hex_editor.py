"""Widget tests for ``HexEditor``."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.hexviewer.hex_editor import HexEditor
from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.select_event import SelectEvent


def test_constructs_and_exposes_panes(tk_root: tk.Tk) -> None:
    model = HexModel(b"Hello, world!")
    editor = HexEditor(tk_root, model)
    assert editor.get_hex_pane() is not None
    assert editor.get_address_pane() is not None
    assert editor.get_ascii_pane() is not None
    assert editor.get_status_pane() is not None


def test_selection_changed_updates_status(tk_root: tk.Tk) -> None:
    model = HexModel(bytes(range(32)))
    editor = HexEditor(tk_root, model)
    editor.selection_changed(SelectEvent(5, SelectEvent.IN))
    status = editor.get_status_pane()
    assert status is not None
    assert status.get_index_text() == "5"
    assert editor.get_selected_index() == 5


def test_selection_changed_respects_navigation(tk_root: tk.Tk) -> None:
    model = HexModel(bytes(range(32)))
    editor = HexEditor(tk_root, model)
    editor.selection_changed(SelectEvent(0, SelectEvent.NEXT))
    assert editor.get_selected_index() == 1
    editor.selection_changed(SelectEvent(16, SelectEvent.UP))
    assert editor.get_selected_index() == 0
    editor.selection_changed(SelectEvent(0, SelectEvent.DOWN))
    assert editor.get_selected_index() == 16


def test_selection_changed_ignores_out_of_range(tk_root: tk.Tk) -> None:
    model = HexModel(bytes(range(4)))
    editor = HexEditor(tk_root, model)
    editor.selection_changed(SelectEvent(0, SelectEvent.PREVIOUS))
    # Index would go to -1; selected_index must stay at default -1.
    assert editor.get_selected_index() == -1
