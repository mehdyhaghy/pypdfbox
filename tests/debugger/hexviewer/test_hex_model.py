"""Tests for ``HexModel`` — exercises the pure-data behaviour fully."""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.hex_changed_event import HexChangedEvent
from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_model_changed_event import (
    HexModelChangedEvent,
)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[HexModelChangedEvent] = []

    def hex_model_changed(self, event: HexModelChangedEvent) -> None:
        self.events.append(event)


def test_size_and_total_line_full_row() -> None:
    model = HexModel(bytes(range(16)))
    assert model.size() == 16
    assert model.total_line() == 1


def test_total_line_partial_row() -> None:
    model = HexModel(bytes(range(17)))
    assert model.size() == 17
    assert model.total_line() == 2


def test_total_line_empty() -> None:
    model = HexModel(b"")
    assert model.size() == 0
    assert model.total_line() == 0


def test_get_byte_returns_unsigned_value() -> None:
    model = HexModel(bytes([0x00, 0xFF, 0x80]))
    assert model.get_byte(0) == 0x00
    assert model.get_byte(1) == 0xFF
    assert model.get_byte(2) == 0x80


def test_get_bytes_for_line_truncates_short_row() -> None:
    model = HexModel(bytes(range(20)))
    line1 = model.get_bytes_for_line(1)
    line2 = model.get_bytes_for_line(2)
    assert line1 == bytes(range(16))
    assert line2 == bytes(range(16, 20))


def test_get_line_chars_replaces_non_printable_with_dot() -> None:
    data = bytes([0x00, 0x1F, 0x20, 0x41, 0x7E, 0x7F, 0xFF])
    model = HexModel(data)
    chars = model.get_line_chars(1)
    assert chars == [".", ".", " ", "A", "~", ".", "."]


def test_line_number_static() -> None:
    assert HexModel.line_number(0) == 1
    assert HexModel.line_number(15) == 1
    assert HexModel.line_number(16) == 2
    assert HexModel.line_number(31) == 2
    assert HexModel.line_number(32) == 3


def test_element_index_in_line_static() -> None:
    assert HexModel.element_index_in_line(0) == 0
    assert HexModel.element_index_in_line(15) == 15
    assert HexModel.element_index_in_line(16) == 0
    assert HexModel.element_index_in_line(17) == 1


def test_update_model_only_fires_on_real_change() -> None:
    model = HexModel(b"\x00\x00")
    recorder = _Recorder()
    model.add_hex_model_change_listener(recorder)

    model.update_model(0, 0x00)
    assert recorder.events == []  # value didn't change

    model.update_model(0, 0x42)
    assert len(recorder.events) == 1
    assert recorder.events[0].get_start_index() == 0
    assert recorder.events[0].get_change_type() == (
        HexModelChangedEvent.SINGLE_CHANGE
    )
    assert model.get_byte(0) == 0x42


def test_update_model_masks_to_byte() -> None:
    model = HexModel(b"\x00")
    model.update_model(0, 0x1FF)
    assert model.get_byte(0) == 0xFF


def test_hex_changed_updates_data_and_fires_event() -> None:
    model = HexModel(b"\x00")
    recorder = _Recorder()
    model.add_hex_model_change_listener(recorder)
    model.hex_changed(HexChangedEvent(0x42, 0))
    assert model.get_byte(0) == 0x42
    assert len(recorder.events) == 1
    assert recorder.events[0].get_start_index() == 0


def test_hex_changed_with_negative_index_still_fires() -> None:
    """Mirror upstream: index=-1 fires a change event but does not mutate."""

    model = HexModel(b"\x00")
    recorder = _Recorder()
    model.add_hex_model_change_listener(recorder)
    model.hex_changed(HexChangedEvent(0x42, -1))
    assert model.get_byte(0) == 0x00
    assert len(recorder.events) == 1
    assert recorder.events[0].get_start_index() == -1


def test_constructor_accepts_bytearray() -> None:
    model = HexModel(bytearray(b"\x01\x02\x03"))
    assert model.size() == 3
    assert model.get_byte(0) == 0x01
