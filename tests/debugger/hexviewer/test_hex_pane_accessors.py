"""Accessor / listener-fan-out tests for ``HexPane`` (parity wave 1308).

Targets the upstream-aligned public methods promoted in this wave:
``get_byte``, ``get_chars``, ``get_index_for_point``,
``get_point_for_index``, ``fire_hex_value_changed`` and
``fire_selection_changed``.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.hexviewer.hex_changed_event import HexChangedEvent
from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_pane import HexPane
from pypdfbox.debugger.hexviewer.hex_view import HexView
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


# ---- get_chars -----------------------------------------------------------


def test_get_chars_returns_two_char_uppercase_hex(tk_root: tk.Tk) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00"))
    assert pane.get_chars(0x00) == "00"
    assert pane.get_chars(0xAB) == "AB"
    assert pane.get_chars(0xFF) == "FF"


def test_get_chars_masks_to_one_byte(tk_root: tk.Tk) -> None:
    """Upstream ``getChars`` ANDs with ``0xFF``; bytes outside the range
    are wrapped to the low 8 bits."""

    pane = HexPane(tk_root, HexModel(b"\x00"))
    assert pane.get_chars(0x1FF) == "FF"


# ---- get_byte ------------------------------------------------------------


def test_get_byte_decodes_two_hex_chars(tk_root: tk.Tk) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00"))
    assert pane.get_byte(["0", "0"]) == 0x00
    assert pane.get_byte(["A", "B"]) == 0xAB
    assert pane.get_byte(["f", "f"]) == 0xFF


def test_get_byte_raises_value_error_for_non_hex(tk_root: tk.Tk) -> None:
    """Upstream throws ``NumberFormatException``; Python equivalent is
    ``ValueError`` from ``int(str, 16)``."""

    pane = HexPane(tk_root, HexModel(b"\x00"))
    with pytest.raises(ValueError):
        pane.get_byte(["Z", "Z"])


def test_get_byte_round_trip_through_get_chars(tk_root: tk.Tk) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00"))
    for b in (0x00, 0x01, 0x7F, 0x80, 0xAB, 0xFF):
        assert pane.get_byte(list(pane.get_chars(b))) == b


# ---- get_index_for_point -------------------------------------------------


def test_get_index_for_point_inside_grid_returns_byte_index(
    tk_root: tk.Tk,
) -> None:
    """A hand-crafted ``(x, y)`` inside the rendered cell at row 1,
    column 0 must yield byte-index 0 (upstream parity)."""

    pane = HexPane(tk_root, HexModel(bytes(range(32))))
    # Column 0 of row 1 — just past the 20-px gutter, within row height.
    x = 20 + HexView.CHAR_WIDTH // 2 + 1
    y = HexView.CHAR_HEIGHT // 2
    assert pane.get_index_for_point((x, y)) == 0


def test_get_index_for_point_second_row_third_element(tk_root: tk.Tk) -> None:
    pane = HexPane(tk_root, HexModel(bytes(range(64))))
    # Row 2, element 2 → byte index 16 + 2 = 18.
    x = 20 + 2 * HexView.CHAR_WIDTH + HexView.CHAR_WIDTH // 2
    y = HexView.CHAR_HEIGHT + HexView.CHAR_HEIGHT // 2
    assert pane.get_index_for_point((x, y)) == 18


def test_get_index_for_point_left_gutter_returns_neg_one(
    tk_root: tk.Tk,
) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00\x01\x02"))
    # Anything in the 20-px left gutter (x <= 20) → -1.
    assert pane.get_index_for_point((0, 5)) == -1
    assert pane.get_index_for_point((20, 5)) == -1


def test_get_index_for_point_right_of_grid_returns_neg_one(
    tk_root: tk.Tk,
) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00\x01\x02"))
    # x >= 16 * CHAR_WIDTH + 20 → past the right edge.
    x = 16 * HexView.CHAR_WIDTH + 20
    assert pane.get_index_for_point((x, 5)) == -1


# ---- get_point_for_index -------------------------------------------------


def test_get_point_for_index_returns_upper_left_of_first_cell(
    tk_root: tk.Tk,
) -> None:
    pane = HexPane(tk_root, HexModel(bytes(range(32))))
    x, y = pane.get_point_for_index(0)
    assert x == HexView.LINE_INSET
    assert y == HexView.CHAR_HEIGHT  # line 1 → y = CHAR_HEIGHT


def test_get_point_for_index_second_row(tk_root: tk.Tk) -> None:
    pane = HexPane(tk_root, HexModel(bytes(range(64))))
    # Index 17 is on row 2, column 1.
    x, y = pane.get_point_for_index(17)
    assert x == HexView.LINE_INSET + HexView.CHAR_WIDTH
    assert y == 2 * HexView.CHAR_HEIGHT


# ---- fire_hex_value_changed ---------------------------------------------


def test_fire_hex_value_changed_notifies_each_listener_once(
    tk_root: tk.Tk,
) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00\x01"))
    r1 = _HexChangeRecorder()
    r2 = _HexChangeRecorder()
    pane.add_hex_change_listeners(r1)
    pane.add_hex_change_listeners(r2)
    pane.fire_hex_value_changed(0xAB, 0)
    assert len(r1.events) == 1
    assert len(r2.events) == 1
    assert r1.events[0].get_new_value() == 0xAB
    assert r1.events[0].get_byte_index() == 0


def test_fire_hex_value_changed_with_no_listeners_is_noop(
    tk_root: tk.Tk,
) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00"))
    # Must not raise on an empty listener list.
    pane.fire_hex_value_changed(0xAB, 0)


# ---- fire_selection_changed ---------------------------------------------


def test_fire_selection_changed_notifies_each_listener_once(
    tk_root: tk.Tk,
) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00\x01"))
    r1 = _SelectionRecorder()
    r2 = _SelectionRecorder()
    pane.add_selection_change_listener(r1)
    pane.add_selection_change_listener(r2)
    event = SelectEvent(1, SelectEvent.IN)
    pane.fire_selection_changed(event)
    assert len(r1.events) == 1
    assert len(r2.events) == 1
    assert r1.events[0] is event
    assert r2.events[0] is event


def test_fire_selection_changed_with_no_listeners_is_noop(
    tk_root: tk.Tk,
) -> None:
    pane = HexPane(tk_root, HexModel(b"\x00"))
    pane.fire_selection_changed(SelectEvent(0, SelectEvent.IN))


# ---- private-alias compatibility ----------------------------------------


def test_private_aliases_still_work(tk_root: tk.Tk) -> None:
    """The ``_fire_*`` private aliases must keep working for existing
    call-sites until they migrate to the public names."""

    pane = HexPane(tk_root, HexModel(b"\x00\x01"))
    sel = _SelectionRecorder()
    hxr = _HexChangeRecorder()
    pane.add_selection_change_listener(sel)
    pane.add_hex_change_listeners(hxr)
    pane._fire_selection_changed(SelectEvent(0, SelectEvent.IN))  # noqa: SLF001
    pane._fire_hex_value_changed(0xAB, 0)  # noqa: SLF001
    assert len(sel.events) == 1
    assert len(hxr.events) == 1
