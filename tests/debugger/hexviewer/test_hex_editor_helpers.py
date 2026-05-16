"""Widget tests for the wave 1309 ``HexEditor`` helpers.

Exercises the promoted ``create_view`` plus the new ``create_jump_dialog``
and ``get_scroll_pane`` accessors. Honours ``PYPDFBOX_SKIP_TK=1`` via the
hexviewer ``tk_root`` fixture (skips when no Tk display is available).
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk

from pypdfbox.debugger.hexviewer.hex_editor import HexEditor
from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_pane import HexPane
from pypdfbox.debugger.hexviewer.status_pane import StatusPane


def test_create_view_alias_points_at_public(tk_root: tk.Tk) -> None:
    """The promoted public ``create_view`` and the legacy ``_create_view``
    alias must resolve to the same function object."""

    assert HexEditor._create_view is HexEditor.create_view


def test_create_view_populates_children_and_status(tk_root: tk.Tk) -> None:
    """``create_view`` (invoked by ``__init__``) wires up the HexPane and
    a StatusPane as direct/indirect children of the editor frame."""

    model = HexModel(bytes(range(64)))
    editor = HexEditor(tk_root, model)

    # The editor frame itself must be a non-None ttk.Frame with children.
    assert editor is not None
    assert isinstance(editor, ttk.Frame)
    assert editor.winfo_children()

    # Status pane is a direct child of the editor.
    status_children = [
        w for w in editor.winfo_children() if isinstance(w, StatusPane)
    ]
    assert len(status_children) == 1

    # Hex pane lives inside the scroll-pane body (a sibling frame).
    scroll = editor.get_scroll_pane()
    hex_children = [
        w for w in scroll.winfo_children() if isinstance(w, HexPane)
    ]
    assert len(hex_children) == 1
    assert hex_children[0] is editor.get_hex_pane()


def test_get_scroll_pane_is_cached_and_hosts_hex_pane(
    tk_root: tk.Tk,
) -> None:
    """``get_scroll_pane`` returns the same Frame instance on repeated
    calls (upstream calls it exactly once from ``createView``)."""

    model = HexModel(b"abcdefghij")
    editor = HexEditor(tk_root, model)

    first = editor.get_scroll_pane()
    second = editor.get_scroll_pane()
    assert first is second
    assert isinstance(first, ttk.Frame)

    # The HexPane lives inside the scroll-pane container.
    hex_pane = editor.get_hex_pane()
    assert hex_pane is not None
    assert hex_pane.master is first


def test_create_jump_dialog_returns_toplevel(tk_root: tk.Tk) -> None:
    """``create_jump_dialog`` returns a fresh Toplevel each call."""

    model = HexModel(bytes(range(8)))
    editor = HexEditor(tk_root, model)

    dialog = editor.create_jump_dialog()
    try:
        assert isinstance(dialog, tk.Toplevel)
        # Title mirrors upstream "Jump to index".
        assert dialog.title() == "Jump to index"
        # Entry + OK button must be reachable for downstream automation.
        assert hasattr(dialog, "_pypdfbox_entry")
        assert hasattr(dialog, "_pypdfbox_ok")
    finally:
        with contextlib.suppress(tk.TclError):
            dialog.destroy()


def test_create_jump_dialog_hex_input_jumps_to_byte_26(
    tk_root: tk.Tk,
) -> None:
    """Entering ``0x1A`` and clicking OK selects byte 26 and tears the
    dialog down. Hex-prefix support is the documented upstream deviation."""

    model = HexModel(bytes(range(64)))
    editor = HexEditor(tk_root, model)

    dialog = editor.create_jump_dialog()
    try:
        entry = dialog._pypdfbox_entry  # type: ignore[attr-defined]
        commit = dialog._pypdfbox_commit  # type: ignore[attr-defined]
        entry.insert(0, "0x1A")
        commit()
    finally:
        # ``commit`` destroys the dialog on success; guard against the
        # alternate path (invalid input) which leaves it open.
        with contextlib.suppress(tk.TclError):
            dialog.destroy()

    assert editor.get_selected_index() == 26
    status = editor.get_status_pane()
    assert status is not None
    assert status.get_index_text() == "26"


def test_create_jump_dialog_decimal_input_jumps(tk_root: tk.Tk) -> None:
    """Decimal input (no ``0x`` prefix) still works — that's the upstream
    semantics, our hex prefix is a strict superset."""

    model = HexModel(bytes(range(64)))
    editor = HexEditor(tk_root, model)

    dialog = editor.create_jump_dialog()
    try:
        entry = dialog._pypdfbox_entry  # type: ignore[attr-defined]
        commit = dialog._pypdfbox_commit  # type: ignore[attr-defined]
        entry.insert(0, "7")
        commit()
    finally:
        with contextlib.suppress(tk.TclError):
            dialog.destroy()

    assert editor.get_selected_index() == 7


def test_create_jump_dialog_out_of_range_input_is_ignored(
    tk_root: tk.Tk,
) -> None:
    """Out-of-range values must leave the editor's selection untouched
    and keep the dialog alive (matches upstream)."""

    model = HexModel(bytes(range(8)))
    editor = HexEditor(tk_root, model)

    dialog = editor.create_jump_dialog()
    try:
        entry = dialog._pypdfbox_entry  # type: ignore[attr-defined]
        commit = dialog._pypdfbox_commit  # type: ignore[attr-defined]
        entry.insert(0, "999")
        commit()
        # Dialog must still exist (commit didn't destroy it).
        assert dialog.winfo_exists()
    finally:
        with contextlib.suppress(tk.TclError):
            dialog.destroy()

    assert editor.get_selected_index() == -1


def test_create_jump_dialog_invalid_input_does_not_raise(
    tk_root: tk.Tk,
) -> None:
    """Non-numeric input is swallowed (no ``ValueError`` to the caller)."""

    model = HexModel(bytes(range(8)))
    editor = HexEditor(tk_root, model)

    dialog = editor.create_jump_dialog()
    try:
        entry = dialog._pypdfbox_entry  # type: ignore[attr-defined]
        commit = dialog._pypdfbox_commit  # type: ignore[attr-defined]
        entry.insert(0, "not-a-number")
        commit()  # must not raise
    finally:
        with contextlib.suppress(tk.TclError):
            dialog.destroy()

    assert editor.get_selected_index() == -1
