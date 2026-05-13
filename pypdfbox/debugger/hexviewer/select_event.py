"""Selection-change event for the hex view."""

from __future__ import annotations


class SelectEvent:
    """Describes a selection-related navigation event in the hex view."""

    NEXT = "next"
    PREVIOUS = "previous"
    UP = "up"
    DOWN = "down"
    NONE = "none"
    IN = "in"
    EDIT = "edit"

    def __init__(self, ind: int, nav: str) -> None:
        self._hex_index = ind
        self._navigation = nav

    def get_hex_index(self) -> int:
        return self._hex_index

    def get_navigation(self) -> str:
        return self._navigation
