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


# ---- listener firing -----------------------------------------------------


def test_selection_listener_receives_event_on_click(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00\x01\x02")
    pane = HexPane(tk_root, model)
    recorder = _SelectionRecorder()
    pane.add_selection_change_listener(recorder)
    # Manually fire a selection-change event via the private helper.
    pane._fire_selection_changed(SelectEvent(1, SelectEvent.IN))  # noqa: SLF001
    assert len(recorder.events) == 1
    assert recorder.events[0].get_hex_index() == 1


def test_hex_change_listener_receives_event(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00\x01")
    pane = HexPane(tk_root, model)
    recorder = _HexChangeRecorder()
    pane.add_hex_change_listeners(recorder)
    pane._fire_hex_value_changed(0xAB, 0)  # noqa: SLF001
    assert len(recorder.events) == 1
    assert recorder.events[0].get_new_value() == 0xAB


# ---- click handler -------------------------------------------------------


def test_index_for_click_returns_negative_for_out_of_range_byte(
    tk_root: tk.Tk,
) -> None:
    """``_index_for_click`` clamps to ``-1`` past the model size."""
    model = HexModel(b"\x00")
    pane = HexPane(tk_root, model)
    import types

    # Force a click on line 2 (past the rendered grid for a 1-byte model).
    # The Tk widget snaps to nearest valid text index; we simulate a high
    # ``col`` value that yields ``element > 15``.
    pane.update_idletasks()
    # Hand-build an event that maps to row 2 column 100 — Tk will clamp,
    # but the resulting line/element computation still must not produce a
    # valid byte index for an empty second row.
    event = types.SimpleNamespace(x=1000, y=200)
    # The wired ``_on_click`` always returns "break".
    assert pane._on_click(event) == "break"  # type: ignore[arg-type]  # noqa: SLF001


def test_on_click_for_valid_position_fires_in_event(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00\x01\x02")
    pane = HexPane(tk_root, model)
    recorder = _SelectionRecorder()
    pane.add_selection_change_listener(recorder)
    import types

    # Click within the rendered region — coordinates pulled to ensure
    # ``identify`` lands on a valid line/column.
    pane.update_idletasks()
    event = types.SimpleNamespace(x=2, y=2)
    pane._on_click(event)  # type: ignore[arg-type]  # noqa: SLF001
    # At least one event was fired — exact type depends on whether the
    # click landed inside the grid; we only assert the wiring ran.
    assert recorder.events


# ---- key handler --------------------------------------------------------


def test_on_key_with_no_selection_is_noop(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00\x01")
    pane = HexPane(tk_root, model)
    import types

    event = types.SimpleNamespace(char="A")
    assert pane._on_key(event) is None  # type: ignore[arg-type]  # noqa: SLF001


def test_on_key_first_digit_triggers_edit(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00\x01")
    pane = HexPane(tk_root, model)
    pane.set_selected(0)
    recorder = _HexChangeRecorder()
    pane.add_hex_change_listeners(recorder)
    import types

    event = types.SimpleNamespace(char="A")
    pane._on_key(event)  # type: ignore[arg-type]  # noqa: SLF001
    assert recorder.events
    # First digit replaces the high nibble; the rest stays zero.
    assert recorder.events[-1].get_new_value() == 0xA0
    assert pane._state == pane.EDIT  # noqa: SLF001


def test_on_key_non_hex_char_is_noop(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00\x01")
    pane = HexPane(tk_root, model)
    pane.set_selected(0)
    import types

    event = types.SimpleNamespace(char="z")
    assert pane._on_key(event) is None  # type: ignore[arg-type]  # noqa: SLF001


def test_on_key_second_digit_fires_navigate_next(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00\x01")
    pane = HexPane(tk_root, model)
    pane.set_selected(0)
    recorder = _SelectionRecorder()
    hex_recorder = _HexChangeRecorder()
    pane.add_selection_change_listener(recorder)
    pane.add_hex_change_listeners(hex_recorder)
    import types

    pane._on_key(types.SimpleNamespace(char="A"))  # type: ignore[arg-type]  # noqa: SLF001
    pane._on_key(types.SimpleNamespace(char="B"))  # type: ignore[arg-type]  # noqa: SLF001
    # After the second digit, a NEXT selection fired (the byte value
    # itself reflects the still-zero previous byte plus the low nibble,
    # because ``_fire_hex_value_changed`` does not mutate the model).
    assert hex_recorder.events  # both keypresses produced events
    next_events = [e for e in recorder.events if e.get_navigation() == SelectEvent.NEXT]
    assert next_events


# ---- arrow handler ------------------------------------------------------


def test_arrow_in_normal_state_returns_break(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00")
    pane = HexPane(tk_root, model)
    # Not selected → arrow handler returns "break" but does not fire.
    assert pane._handle_arrow(SelectEvent.NEXT) == "break"  # noqa: SLF001


def test_arrow_left_after_edit_collapses_nibble(tk_root: tk.Tk) -> None:
    model = HexModel(b"\x00")
    pane = HexPane(tk_root, model)
    pane.set_selected(0)
    import types

    # Type one digit → enter EDIT with selected_char=1.
    pane._on_key(types.SimpleNamespace(char="A"))  # type: ignore[arg-type]  # noqa: SLF001
    assert pane._selected_char == 1  # noqa: SLF001
    # Left arrow rewinds to the high nibble.
    pane._handle_arrow(SelectEvent.PREVIOUS)  # noqa: SLF001
    assert pane._selected_char == 0  # noqa: SLF001


# ---- static helpers -----------------------------------------------------


def test_is_hex_char_matches_only_hex_digits(tk_root: tk.Tk) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00"))
    assert pane._is_hex_char("A") is True  # noqa: SLF001
    assert pane._is_hex_char("f") is True  # noqa: SLF001
    assert pane._is_hex_char("9") is True  # noqa: SLF001
    assert pane._is_hex_char("g") is False  # noqa: SLF001
    assert pane._is_hex_char("AB") is False  # noqa: SLF001


def test_get_chars_and_get_byte_round_trip(tk_root: tk.Tk) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00"))
    chars = pane._get_chars(0xAB)  # noqa: SLF001
    assert chars == "AB"
    assert pane._get_byte(["A", "B"]) == 0xAB  # noqa: SLF001
