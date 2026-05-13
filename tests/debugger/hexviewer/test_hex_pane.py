"""Widget tests for ``HexPane``."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.hexviewer.hex_change_listener import HexChangeListener  # noqa: F401
from pypdfbox.debugger.hexviewer.hex_changed_event import HexChangedEvent
from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_pane import HexPane
from pypdfbox.debugger.hexviewer.select_event import SelectEvent


class _SelectionRecorder:
    def __init__(self) -> None:
        self.events: list[SelectEvent] = []

    def selection_changed(self, event: SelectEvent) -> None:
        self.events.append(event)


class _HexChangeRecorder:
    def __init__(self) -> None:
        self.events: list[HexChangedEvent] = []

    def hex_changed(self, event: HexChangedEvent) -> None:
        self.events.append(event)


def test_renders_bytes_as_hex(tk_root: tk.Tk) -> None:
    model = HexModel(bytes([0x00, 0x01, 0xFF]))
    pane = HexPane(tk_root, model)
    text = pane.get("1.0", "end-1c")
    # First row should start with "00 01 FF" (and end there because only 3 bytes).
    first_line = text.splitlines()[0]
    assert first_line.startswith("00 01 FF")


def test_set_selected_updates_state(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00\x01\x02")
    pane = HexPane(tk_root, model)
    pane.set_selected(1)
    ranges = pane.tag_ranges("selected")
    assert ranges


def test_model_change_triggers_redraw(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00\x00")
    pane = HexPane(tk_root, model)
    model.update_model(0, 0xAB)
    text = pane.get("1.0", "end-1c")
    assert text.startswith("AB 00")
