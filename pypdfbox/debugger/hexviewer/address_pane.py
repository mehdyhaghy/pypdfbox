"""Left-hand address column for the hex viewer.

Tkinter port of ``org.apache.pdfbox.debugger.hexviewer.AddressPane``. The
Swing original is custom-painted onto a ``JComponent``; here we use a
read-only ``tk.Text`` widget whose contents are regenerated whenever the
selected line changes. Tag-driven styling reproduces the bold/highlighted
appearance of the selected address.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from pypdfbox.debugger.hexviewer.hex_model import HexModel


class AddressPane(tk.Text):
    """Shows the offset of every 16-byte row of the hex view."""

    def __init__(self, master: tk.Misc, total: int) -> None:
        self._total_line = total
        self._selected_line = -1
        self._selected_index = -1

        # Use a fixed-width font so column alignment lines up with HexPane.
        self._font = tkfont.Font(family="Courier", size=11)
        self._bold = tkfont.Font(
            family="Courier", size=11, weight=tkfont.BOLD
        )

        super().__init__(
            master,
            width=10,
            height=max(total + 1, 1),
            font=self._font,
            borderwidth=0,
            wrap="none",
            takefocus=0,
        )

        # Apply selection highlight to the "selected" tag.
        self.tag_configure(
            "selected", foreground="blue", font=self._bold
        )

        self._render()
        self.configure(state="disabled")

    # ------------------------------------------------------------------ API

    def set_selected(self, index: int) -> None:
        """Mark the row containing *index* as selected and redraw."""

        if index == self._selected_index:
            return
        self._selected_line = HexModel.line_number(index)
        self._selected_index = index
        self._render()

    # -------------------------------------------------------------- helpers

    def _render(self) -> None:
        """Rebuild the body of the text widget."""

        self.configure(state="normal")
        self.delete("1.0", "end")
        for line in range(1, self._total_line + 1):
            if line == self._selected_line:
                offset = f"{self._selected_index:08X}"
                start = self.index("end-1c")
                self.insert("end", offset + "\n")
                end = self.index("end-1c")
                self.tag_add("selected", start, end)
            else:
                self.insert("end", f"{(line - 1) * 16:08X}\n")
        self.configure(state="disabled")
