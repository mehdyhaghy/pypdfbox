"""Pure-data model backing the hex viewer.

Port of ``org.apache.pdfbox.debugger.hexviewer.HexModel``. The class keeps a
mutable byte buffer plus a list of ``HexModelChangeListener`` callbacks; the
Tkinter widgets register themselves on construction so any mutation triggers
a redraw without their having to share state.
"""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.hex_changed_event import HexChangedEvent
from pypdfbox.debugger.hexviewer.hex_model_change_listener import (
    HexModelChangeListener,
)
from pypdfbox.debugger.hexviewer.hex_model_changed_event import (
    HexModelChangedEvent,
)


class HexModel:
    """A model for the hex viewer holding bytes and dispatching changes."""

    def __init__(self, bytes_: bytes | bytearray | None) -> None:
        # Mirror upstream: store as a mutable list of byte values (0..255).
        if bytes_ is None:
            self._data: list[int] = []
        else:
            self._data = [b & 0xFF for b in bytes_]
        self._model_change_listeners: list[HexModelChangeListener] = []

    # ------------------------------------------------------------------ data

    def get_byte(self, index: int) -> int:
        """Return the byte (0..255) at *index*."""

        return self._data[index]

    def get_line_chars(self, line_number: int) -> list[str]:
        """Return up to 16 printable-ASCII characters for *line_number* (1-based).

        Non-printable bytes are replaced with ``.``, mirroring upstream.
        """

        start = (line_number - 1) * 16
        length = min(len(self._data) - start, 16)
        chars: list[str] = []
        for i in range(length):
            byte_value = self._data[start + i] & 0xFF
            c = chr(byte_value)
            if not self._is_ascii_printable(c):
                c = "."
            chars.append(c)
        return chars

    def get_bytes_for_line(self, line_number: int) -> bytes:
        index = (line_number - 1) * 16
        length = min(len(self._data) - index, 16)
        return bytes(self._data[index : index + length])

    def size(self) -> int:
        return len(self._data)

    def total_line(self) -> int:
        size = self.size()
        return size // 16 + 1 if size % 16 != 0 else size // 16

    # --------------------------------------------------------------- helpers

    @staticmethod
    def line_number(index: int) -> int:
        element_no = index + 1
        return (
            element_no // 16 + 1 if element_no % 16 != 0 else element_no // 16
        )

    @staticmethod
    def element_index_in_line(index: int) -> int:
        return index % 16

    @staticmethod
    def _is_ascii_printable(ch: str) -> bool:
        if not ch:
            return False
        code = ord(ch)
        return 32 <= code < 127

    # --------------------------------------------------------------- updates

    def add_hex_model_change_listener(
        self, listener: HexModelChangeListener
    ) -> None:
        self._model_change_listeners.append(listener)

    def update_model(self, index: int, value: int) -> None:
        value &= 0xFF
        if self._data[index] != value:
            self._data[index] = value
            self._fire_model_changed(index)

    # ----------------------------------------- HexChangeListener interface

    def hex_changed(self, event: HexChangedEvent) -> None:
        index = event.get_byte_index()
        if index != -1 and self.get_byte(index) != event.get_new_value():
            self._data[index] = event.get_new_value() & 0xFF
        self._fire_model_changed(index)

    # ----------------------------------------------------------- dispatch

    def _fire_model_changed(self, index: int) -> None:
        evt = HexModelChangedEvent(index, HexModelChangedEvent.SINGLE_CHANGE)
        for listener in self._model_change_listeners:
            listener.hex_model_changed(evt)
