"""Event describing a single byte change emitted from the hex pane."""

from __future__ import annotations


class HexChangedEvent:
    """Event for byte-value changes originating in the hex pane."""

    def __init__(self, new_value: int, byte_index: int) -> None:
        # Match the upstream byte semantics: keep the value in 0..255.
        self._new_value = new_value & 0xFF
        self._byte_index = byte_index

    def get_new_value(self) -> int:
        return self._new_value

    def get_byte_index(self) -> int:
        return self._byte_index
