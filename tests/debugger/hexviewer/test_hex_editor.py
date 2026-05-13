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


def test_scrollbar_sync_callbacks_fire(tk_root: tk.Tk) -> None:
    """The internal scrollbar wiring relays yview/yscrollcommand calls
    across the three column panes; exercising both directions ensures the
    closures are reached."""
    model = HexModel(bytes(range(64)))
    editor = HexEditor(tk_root, model)
    editor.update_idletasks()

    hex_pane = editor.get_hex_pane()
    address_pane = editor.get_address_pane()
    ascii_pane = editor.get_ascii_pane()
    assert hex_pane is not None
    assert address_pane is not None
    assert ascii_pane is not None

    # Drive the hex pane's yview to fire ``_on_scrollbar_set``.
    hex_pane.yview_moveto(0.5)
    editor.update_idletasks()

    # Drive the scrollbar itself to fire ``_on_yview``: ``yview_moveto``
    # is the canonical "scroll-to-fraction" command exposed by Tk's
    # scrollbar -> bound command.
    # ``scrollbar.invoke`` doesn't exist for a Scrollbar; instead we
    # query the configured command and call it directly.
    body = hex_pane.master  # the inner Frame
    # Find the scrollbar child by traversing the body's children.
    scrollbars = [
        w for w in body.winfo_children() if isinstance(w, tk.ttk.Scrollbar)
    ]
    assert scrollbars
    scrollbar = scrollbars[0]
    cmd = scrollbar.cget("command")
    # Tk reports the command name; calling it via tk.call works.
    if cmd:
        scrollbar.tk.call(cmd, "moveto", "0.25")
    editor.update_idletasks()
