"""Event describing a change to ``HexModel`` data."""

from __future__ import annotations


class HexModelChangedEvent:
    """Describes a change to the underlying ``HexModel`` byte buffer."""

    BULK_CHANGE = 1
    SINGLE_CHANGE = 2

    def __init__(self, start_index: int, change_type: int) -> None:
        self._start_index = start_index
        self._change_type = change_type

    def get_start_index(self) -> int:
        return self._start_index

    def get_change_type(self) -> int:
        return self._change_type
