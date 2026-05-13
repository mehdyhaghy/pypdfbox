"""Tests for ``HexModelChangedEvent``."""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.hex_model_changed_event import (
    HexModelChangedEvent,
)


def test_accessors() -> None:
    event = HexModelChangedEvent(7, HexModelChangedEvent.SINGLE_CHANGE)
    assert event.get_start_index() == 7
    assert event.get_change_type() == HexModelChangedEvent.SINGLE_CHANGE


def test_change_type_constants_distinct() -> None:
    assert HexModelChangedEvent.SINGLE_CHANGE != HexModelChangedEvent.BULK_CHANGE
