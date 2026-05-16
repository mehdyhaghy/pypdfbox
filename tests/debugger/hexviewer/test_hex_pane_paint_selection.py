"""Tests for the painting / selection fast paths on ``HexPane`` (wave 1312).

Targets the upstream-aligned public methods promoted in this wave:
``get_selected_string``, ``is_hex_char``, ``paint_component``,
``paint_in_edit``, and ``put_in_selected``.
"""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_pane import HexPane


# ---- is_hex_char ---------------------------------------------------------


def test_is_hex_char_matches_only_hex_digits(tk_root: tk.Tk) -> None:
    """Single-char hex digits (0-9, a-f, A-F) match; everything else does not."""

    pane = HexPane(tk_root, HexModel(b"\x00"))
    # Direct call on the public method.
    assert HexPane.is_hex_char("0") is True
    assert HexPane.is_hex_char("9") is True
    assert HexPane.is_hex_char("a") is True
    assert HexPane.is_hex_char("F") is True
    assert HexPane.is_hex_char("g") is False
    assert HexPane.is_hex_char("Z") is False
    assert HexPane.is_hex_char("") is False
    assert HexPane.is_hex_char("AB") is False
    # Instance access must also work (legacy call sites).
    assert pane.is_hex_char("c") is True
    # Private alias must still resolve to the same predicate.
    assert pane._is_hex_char("c") is True  # noqa: SLF001


# ---- get_selected_string -------------------------------------------------


def test_get_selected_string_returns_styled_descriptor(tk_root: tk.Tk) -> None:
    """Tkinter has no ``AttributedString``; the descriptor dict carries
    the same triple (text, bold font, selected colour) that upstream
    encodes via ``TextAttribute.FONT`` / ``TextAttribute.FOREGROUND``."""

    pane = HexPane(tk_root, HexModel(b"\xab"))
    desc = pane.get_selected_string("AB")
    assert desc["text"] == "AB"
    assert desc["foreground"] == "blue"
    # The font must be the bold variant used elsewhere by _render.
    assert desc["font"] is pane._bold  # noqa: SLF001


# ---- put_in_selected -----------------------------------------------------


def test_put_in_selected_marks_index_and_state(tk_root: tk.Tk) -> None:
    """``put_in_selected`` flips state to SELECTED, resets the half-byte
    cursor, and stores the byte index — matching upstream behaviour."""

    pane = HexPane(tk_root, HexModel(b"\x00\x01\x02\x03"))
    pane.put_in_selected(2)
    assert pane._state == HexPane.SELECTED  # noqa: SLF001
    assert pane._selected_index == 2  # noqa: SLF001
    assert pane._selected_char == 0  # noqa: SLF001
    # The private alias still works for legacy call-sites.
    pane._put_in_selected(1)  # noqa: SLF001
    assert pane._selected_index == 1  # noqa: SLF001


# ---- paint_component -----------------------------------------------------


def test_paint_component_rerenders_without_error(tk_root: tk.Tk) -> None:
    """``paint_component`` rerenders the grid; calling it twice must
    leave the Text widget content stable (no double-insertion)."""

    pane = HexPane(tk_root, HexModel(b"\x00\xff"))
    pane.paint_component()
    first = pane.get("1.0", "end-1c")
    pane.paint_component()
    second = pane.get("1.0", "end-1c")
    assert first == second
    # Row 1 shows the two hex pairs.
    assert "00" in first
    assert "FF" in first


# ---- paint_in_edit -------------------------------------------------------


def test_paint_in_edit_switches_state_to_edit(tk_root: tk.Tk) -> None:
    """``paint_in_edit`` puts the pane into EDIT state at the given index
    so the cell will be drawn with the half-byte cursor tags."""

    pane = HexPane(tk_root, HexModel(b"\x00\x01\x02"))
    pane.paint_in_edit(0xAB, 1)
    assert pane._state == HexPane.EDIT  # noqa: SLF001
    assert pane._selected_index == 1  # noqa: SLF001
