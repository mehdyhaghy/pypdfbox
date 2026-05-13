"""Tests for the ``HexChangeListener`` protocol."""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.hex_change_listener import HexChangeListener
from pypdfbox.debugger.hexviewer.hex_changed_event import HexChangedEvent


class _Recorder:
    def __init__(self) -> None:
        self.events: list[HexChangedEvent] = []

    def hex_changed(self, event: HexChangedEvent) -> None:
        self.events.append(event)


def test_recorder_satisfies_protocol() -> None:
    recorder = _Recorder()
    assert isinstance(recorder, HexChangeListener)


def test_callback_invoked_with_event() -> None:
    recorder = _Recorder()
    event = HexChangedEvent(0x42, 3)
    recorder.hex_changed(event)
    assert recorder.events == [event]
