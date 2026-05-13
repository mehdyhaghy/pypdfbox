"""Listener protocol for ``SelectEvent``."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pypdfbox.debugger.hexviewer.select_event import SelectEvent


@runtime_checkable
class SelectionChangeListener(Protocol):
    """Receives selection-change notifications from the hex view."""

    def selection_changed(self, event: SelectEvent) -> None:
        ...
