"""Tests for ``SelectEvent``."""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.select_event import SelectEvent


def test_accessors() -> None:
    event = SelectEvent(12, SelectEvent.NEXT)
    assert event.get_hex_index() == 12
    assert event.get_navigation() == SelectEvent.NEXT


def test_navigation_constants() -> None:
    for value in (
        SelectEvent.NEXT,
        SelectEvent.PREVIOUS,
        SelectEvent.UP,
        SelectEvent.DOWN,
        SelectEvent.NONE,
        SelectEvent.IN,
        SelectEvent.EDIT,
    ):
        assert isinstance(value, str)
    # All constants should be distinct.
    assert (
        len(
            {
                SelectEvent.NEXT,
                SelectEvent.PREVIOUS,
                SelectEvent.UP,
                SelectEvent.DOWN,
                SelectEvent.NONE,
                SelectEvent.IN,
                SelectEvent.EDIT,
            }
        )
        == 7
    )
