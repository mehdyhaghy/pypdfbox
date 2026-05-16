"""Right-hand ASCII rendering pane.

Tkinter port of ``org.apache.pdfbox.debugger.hexviewer.ASCIIPane``. Each row
shows up to 16 printable-ASCII characters; non-printable bytes are rendered
as ``.``. The selected byte (forwarded from ``HexPane``) is highlighted via
a ``Text`` tag.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_model_changed_event import (
    HexModelChangedEvent,
)


class ASCIIPane(tk.Text):
    """Shows the printable-ASCII view of a ``HexModel``."""

    def __init__(self, master: tk.Misc, model: HexModel) -> None:
        self._model = model
        self._selected_line = -1
        self._selected_index_in_line = 0

        self._font = tkfont.Font(family="Courier", size=11)
        self._bold = tkfont.Font(
            family="Courier", size=11, weight=tkfont.BOLD
        )

        super().__init__(
            master,
            width=16,
            height=max(model.total_line() + 1, 1),
            font=self._font,
            wrap="none",
            borderwidth=0,
            takefocus=0,
        )
        self.tag_configure(
            "selected", foreground="blue", font=self._bold
        )

        model.add_hex_model_change_listener(self)

        self._render()
        self.configure(state="disabled")

    # ----------------------------------------------------------- listeners

    def hex_model_changed(self, event: HexModelChangedEvent) -> None:  # noqa: ARG002
        self.paint_component()

    # ------------------------------------------------------------------ API

    def set_selected(self, index: int) -> None:
        self._selected_line = HexModel.line_number(index)
        self._selected_index_in_line = HexModel.element_index_in_line(index)
        self.paint_component()

    # ------------------------------------------------------------ rendering

    def paint_component(self) -> None:
        """Repaint every visible line.

        Upstream Swing iterates over the visible-rect line range; the Tk
        ``Text`` widget already clips lines outside the viewport, so we
        rewrite the whole buffer and let Tk handle visibility. The selected
        line is delegated to :meth:`paint_in_selected`, matching the
        upstream method split.
        """
        self.configure(state="normal")
        self.delete("1.0", "end")
        for line in range(1, self._model.total_line() + 1):
            line_start = self.index("end-1c")
            if line == self._selected_line:
                self.paint_in_selected(line, line_start)
            else:
                chars = self._model.get_line_chars(line)
                self.insert("end", "".join(chars) + "\n")
        self.configure(state="disabled")

    def paint_in_selected(self, line: int, line_start: str) -> None:
        """Render the selected line and highlight the selected character.

        :param line: 1-based line number being rendered.
        :param line_start: Tk ``Text`` index where the line begins (used
            as the offset for the ``selected`` tag).
        """
        chars = self._model.get_line_chars(line)
        self.insert("end", "".join(chars) + "\n")
        if 0 <= self._selected_index_in_line < len(chars):
            sel_start = f"{line_start}+{self._selected_index_in_line}c"
            sel_end = f"{line_start}+{self._selected_index_in_line + 1}c"
            self.tag_add("selected", sel_start, sel_end)

    # Backwards-compatible alias for the previous private helper name.
    _render = paint_component
