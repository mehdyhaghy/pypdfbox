"""Tests for the newly-promoted paint methods on :class:`AddressPane`."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.hexviewer.address_pane import AddressPane


def test_paint_component_renders_offsets(tk_root: tk.Tk) -> None:
    pane = AddressPane(tk_root, total=4)
    # __init__ already invoked paint_component; reinvoke directly to
    # confirm the public spelling produces the same output.
    pane.configure(state="normal")
    pane.delete("1.0", "end")
    pane.paint_component()
    text = pane.get("1.0", "end-1c")
    lines = text.splitlines()
    assert lines == ["00000000", "00000010", "00000020", "00000030"]


def test_paint_selected_inserts_index_with_tag(tk_root: tk.Tk) -> None:
    pane = AddressPane(tk_root, total=3)
    pane.set_selected(0x25)  # row 3
    text = pane.get("1.0", "end-1c").splitlines()
    # Row 3 (0-indexed 2) should display the absolute byte offset.
    assert text[2] == "00000025"
    # The "selected" tag must cover the highlighted row.
    ranges = pane.tag_ranges("selected")
    assert ranges


def test_paint_component_alias_matches_public_method() -> None:
    # The pre-rename private spelling is preserved as an alias so
    # existing callers (notably the parity tool) still resolve.
    assert AddressPane._render is AddressPane.paint_component
