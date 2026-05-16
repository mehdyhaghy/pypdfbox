"""Tests for ``HexPane.set_default`` (mirrors upstream ``setDefault``)."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_pane import HexPane


def _make_pane(tk_root: tk.Tk, *, size: int = 32) -> HexPane:
    model = HexModel(bytes(range(size)))
    return HexPane(tk_root, model)


def test_set_default_resets_state_to_normal(tk_root: tk.Tk) -> None:
    pane = _make_pane(tk_root)
    pane.put_in_selected(3)
    pane.paint_in_edit(0xAB, 3)
    assert pane._state == HexPane.EDIT
    pane.set_default()
    assert pane._state == HexPane.NORMAL


def test_set_default_resets_selected_char_to_zero(tk_root: tk.Tk) -> None:
    pane = _make_pane(tk_root)
    pane.put_in_selected(5)
    # Simulate the first half of a two-digit edit having been typed.
    pane._state = HexPane.EDIT
    pane._selected_char = 1
    pane.set_default()
    assert pane._selected_char == 0


def test_set_default_rerenders_pane(tk_root: tk.Tk) -> None:
    pane = _make_pane(tk_root)
    pane.put_in_selected(7)
    pane.paint_in_edit(0xCD, 7)
    # After set_default the previously-tagged "edit_high"/"edit_low"
    # ranges should be gone -- _render is invoked with the cleared state.
    pane.set_default()
    assert not pane.tag_ranges("edit_high")
    assert not pane.tag_ranges("edit_low")
