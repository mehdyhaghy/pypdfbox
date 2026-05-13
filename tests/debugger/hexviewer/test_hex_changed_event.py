"""Tests for ``HexChangedEvent``."""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.hex_changed_event import HexChangedEvent


def test_basic_accessors() -> None:
    event = HexChangedEvent(0x7F, 5)
    assert event.get_new_value() == 0x7F
    assert event.get_byte_index() == 5


def test_new_value_is_masked_to_byte() -> None:
    assert HexChangedEvent(0x1FF, 0).get_new_value() == 0xFF
    assert HexChangedEvent(-1, 0).get_new_value() == 0xFF
