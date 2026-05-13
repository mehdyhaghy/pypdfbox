"""Tests for ``SelectionChangeListener``."""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.select_event import SelectEvent
from pypdfbox.debugger.hexviewer.selection_change_listener import (
    SelectionChangeListener,
)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[SelectEvent] = []

    def selection_changed(self, event: SelectEvent) -> None:
        self.events.append(event)


def test_recorder_satisfies_protocol() -> None:
    assert isinstance(_Recorder(), SelectionChangeListener)


def test_callback_records_event() -> None:
    recorder = _Recorder()
    evt = SelectEvent(3, SelectEvent.IN)
    recorder.selection_changed(evt)
    assert recorder.events == [evt]
