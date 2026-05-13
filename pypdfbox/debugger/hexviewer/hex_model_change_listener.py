"""Listener protocol for ``HexModelChangedEvent``."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pypdfbox.debugger.hexviewer.hex_model_changed_event import (
    HexModelChangedEvent,
)


@runtime_checkable
class HexModelChangeListener(Protocol):
    """Receives ``HexModel`` change notifications."""

    def hex_model_changed(self, event: HexModelChangedEvent) -> None:
        ...
