"""Central hex-dump pane.

Tkinter port of ``org.apache.pdfbox.debugger.hexviewer.HexPane``. Each row
holds 16 two-digit hex values plus separating spaces. Click and keyboard
events fire ``SelectEvent`` and ``HexChangedEvent`` notifications via the
listener lists exactly as upstream.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from pypdfbox.debugger.hexviewer.hex_change_listener import HexChangeListener
from pypdfbox.debugger.hexviewer.hex_changed_event import HexChangedEvent
from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_model_changed_event import (
    HexModelChangedEvent,
)
from pypdfbox.debugger.hexviewer.select_event import SelectEvent
from pypdfbox.debugger.hexviewer.selection_change_listener import (
    SelectionChangeListener,
)


class HexPane(tk.Text):
    """Shows the byte contents of a ``HexModel`` as a 16-column hex grid."""

    EDIT = 2
    SELECTED = 1
    NORMAL = 0

    # Per-byte cell width: ``"XX "`` -> 3 columns.
    _CELL_WIDTH = 3

    def __init__(self, master: tk.Misc, model: HexModel) -> None:
        self._model = model
        self._selected_index = -1
        self._state = self.NORMAL
        self._selected_char = 0

        self._hex_change_listeners: list[HexChangeListener] = []
        self._selection_change_listeners: list[SelectionChangeListener] = []

        self._font = tkfont.Font(family="Courier", size=11)
        self._bold = tkfont.Font(
            family="Courier", size=11, weight=tkfont.BOLD
        )

        super().__init__(
            master,
            width=16 * self._CELL_WIDTH,
            height=max(model.total_line() + 1, 1),
            font=self._font,
            wrap="none",
            borderwidth=0,
        )

        self.tag_configure(
            "selected", foreground="blue", font=self._bold
        )
        self.tag_configure(
            "edit_high", foreground="blue", font=self._bold
        )
        self.tag_configure("edit_low", font=self._bold)

        self._render()
        self.configure(state="disabled")

        # Listen for any subsequent model changes so the view stays in sync.
        model.add_hex_model_change_listener(self)

        # Mouse + keyboard wiring (upstream MouseListener / KeyListener).
        self.bind("<Button-1>", self._on_click)
        self.bind("<Key>", self._on_key)
        self.bind("<Left>", lambda _e: self._handle_arrow(SelectEvent.PREVIOUS))
        self.bind("<Right>", lambda _e: self._handle_arrow(SelectEvent.NEXT))
        self.bind("<Up>", lambda _e: self._handle_arrow(SelectEvent.UP))
        self.bind("<Down>", lambda _e: self._handle_arrow(SelectEvent.DOWN))

    # ------------------------------------------------------------- listeners

    def add_selection_change_listener(
        self, listener: SelectionChangeListener
    ) -> None:
        self._selection_change_listeners.append(listener)

    def add_hex_change_listeners(self, listener: HexChangeListener) -> None:
        self._hex_change_listeners.append(listener)

    def _fire_selection_changed(self, event: SelectEvent) -> None:
        for listener in self._selection_change_listeners:
            listener.selection_changed(event)

    def _fire_hex_value_changed(self, value: int, index: int) -> None:
        evt = HexChangedEvent(value, index)
        for listener in self._hex_change_listeners:
            listener.hex_changed(evt)

    # ---------------------------------------------------------------- model

    def hex_model_changed(self, event: HexModelChangedEvent) -> None:  # noqa: ARG002
        self._render()

    # -------------------------------------------------------- selection API

    def set_selected(self, index: int) -> None:
        if index != self._selected_index:
            self._put_in_selected(index)

    def _put_in_selected(self, index: int) -> None:
        self._state = self.SELECTED
        self._selected_char = 0
        self._selected_index = index
        self._render()
        self.focus_set()

    # ------------------------------------------------------------ rendering

    def _render(self) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        for line in range(1, self._model.total_line() + 1):
            row_bytes = self._model.get_bytes_for_line(line)
            index = (line - 1) * 16
            for i, by in enumerate(row_bytes):
                cell = f"{by & 0xFF:02X}"
                start = self.index("end-1c")
                self.insert("end", cell)
                end = self.index("end-1c")
                if (
                    self._selected_index == index
                    and self._state == self.SELECTED
                ):
                    self.tag_add("selected", start, end)
                elif (
                    self._selected_index == index
                    and self._state == self.EDIT
                ):
                    high_end = f"{start}+1c"
                    if self._selected_char == 0:
                        self.tag_add("edit_high", start, high_end)
                        self.tag_add("edit_low", high_end, end)
                    else:
                        self.tag_add("edit_low", start, high_end)
                        self.tag_add("edit_high", high_end, end)
                # trailing separator if not last column
                if i != len(row_bytes) - 1:
                    self.insert("end", " ")
                index += 1
            self.insert("end", "\n")
        self.configure(state="disabled")

    # --------------------------------------------------------------- events

    def _index_for_click(self, event: tk.Event) -> int:
        """Map a click point to a 0-based byte index, or ``-1``."""

        try:
            text_index = self.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return -1
        line_str, col_str = text_index.split(".")
        line = int(line_str)
        col = int(col_str)
        if line < 1 or line > self._model.total_line():
            return -1
        element = col // self._CELL_WIDTH
        if element < 0 or element > 15:
            return -1
        index = (line - 1) * 16 + element
        if index >= self._model.size():
            return -1
        return index

    def _on_click(self, event: tk.Event) -> str:
        index = self._index_for_click(event)
        if index == -1:
            self._fire_selection_changed(SelectEvent(-1, SelectEvent.NONE))
        else:
            self._fire_selection_changed(SelectEvent(index, SelectEvent.IN))
        return "break"

    def _handle_arrow(self, navigation: str) -> str:
        if self._state in (self.SELECTED, self.EDIT):
            if (
                navigation == SelectEvent.PREVIOUS
                and self._state == self.EDIT
                and self._selected_char == 1
            ):
                self._selected_char = 0
                self._render()
            else:
                self._fire_selection_changed(
                    SelectEvent(self._selected_index, navigation)
                )
        return "break"

    def _on_key(self, event: tk.Event) -> str | None:
        if self._selected_index == -1 or not event.char:
            return None
        c = event.char
        if not self._is_hex_char(c):
            return None
        previous_byte = self._model.get_byte(self._selected_index)
        chars = list(self._get_chars(previous_byte))
        chars[self._selected_char] = c.upper()
        edit_byte = self._get_byte(chars)
        if self._selected_char == 0:
            self._state = self.EDIT
            self._selected_char = 1
            self._fire_hex_value_changed(edit_byte, self._selected_index)
        else:
            self._fire_hex_value_changed(edit_byte, self._selected_index)
            self._fire_selection_changed(
                SelectEvent(self._selected_index, SelectEvent.NEXT)
            )
        return "break"

    # ----------------------------------------------------------- byte tools

    @staticmethod
    def _is_hex_char(c: str) -> bool:
        return len(c) == 1 and c in "0123456789abcdefABCDEF"

    @staticmethod
    def _get_chars(b: int) -> str:
        return f"{b & 0xFF:02X}"

    @staticmethod
    def _get_byte(chars: list[str]) -> int:
        return int("".join(chars), 16) & 0xFF
