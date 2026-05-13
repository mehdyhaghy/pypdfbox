"""Tests for ``HexModelChangeListener``."""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.hex_model_change_listener import (
    HexModelChangeListener,
)
from pypdfbox.debugger.hexviewer.hex_model_changed_event import (
    HexModelChangedEvent,
)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[HexModelChangedEvent] = []

    def hex_model_changed(self, event: HexModelChangedEvent) -> None:
        self.events.append(event)


def test_recorder_satisfies_protocol() -> None:
    assert isinstance(_Recorder(), HexModelChangeListener)


def test_callback_records_event() -> None:
    recorder = _Recorder()
    evt = HexModelChangedEvent(2, HexModelChangedEvent.SINGLE_CHANGE)
    recorder.hex_model_changed(evt)
    assert recorder.events == [evt]
