"""Listener protocol for ``HexChangedEvent``."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pypdfbox.debugger.hexviewer.hex_changed_event import HexChangedEvent


@runtime_checkable
class HexChangeListener(Protocol):
    """Receives byte-value change notifications from the hex pane."""

    def hex_changed(self, event: HexChangedEvent) -> None:
        ...
