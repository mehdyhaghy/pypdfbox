"""Hex-viewer composition frame.

Tkinter port of ``org.apache.pdfbox.debugger.hexviewer.HexEditor``. Glues
the address / hex / ASCII panes together inside a scrolling area, wires up
listener fan-out, and hosts the ``Ctrl+G`` jump-to-index dialog.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk

from pypdfbox.debugger.hexviewer.address_pane import AddressPane
from pypdfbox.debugger.hexviewer.ascii_pane import ASCIIPane
from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_pane import HexPane
from pypdfbox.debugger.hexviewer.select_event import SelectEvent
from pypdfbox.debugger.hexviewer.status_pane import StatusPane
from pypdfbox.debugger.hexviewer.upper_pane import UpperPane


class HexEditor(ttk.Frame):
    """Composite widget hosting every hex-viewer sub-pane."""

    def __init__(self, master: tk.Misc, model: HexModel) -> None:
        super().__init__(master)
        self._model = model
        self._selected_index = -1

        self._hex_pane: HexPane | None = None
        self._ascii_pane: ASCIIPane | None = None
        self._address_pane: AddressPane | None = None
        self._status_pane: StatusPane | None = None

        self._create_view()

    # ----------------------------------------------------------- creation

    def _create_view(self) -> None:
        upper_pane = UpperPane(self)
        upper_pane.grid(row=0, column=0, sticky="ew")

        # Scrollable middle row hosting the three column panes.
        body = ttk.Frame(self)
        body.grid(row=1, column=0, sticky="nsew")

        self._address_pane = AddressPane(body, self._model.total_line())
        self._hex_pane = HexPane(body, self._model)
        self._ascii_pane = ASCIIPane(body, self._model)

        self._hex_pane.add_hex_change_listeners(self._model)

        scrollbar = ttk.Scrollbar(body, orient="vertical")
        scrollbar.grid(row=0, column=3, sticky="ns")

        self._address_pane.grid(row=0, column=0, sticky="nsw")
        self._hex_pane.grid(row=0, column=1, sticky="nsew")
        self._ascii_pane.grid(row=0, column=2, sticky="nse")

        # Synchronise vertical scrolling across all three text panes.
        def _on_yview(*args: str) -> None:
            self._address_pane.yview(*args)
            self._hex_pane.yview(*args)
            self._ascii_pane.yview(*args)

        def _on_scrollbar_set(first: str, last: str) -> None:
            scrollbar.set(first, last)
            self._address_pane.yview_moveto(first)
            self._ascii_pane.yview_moveto(first)

        scrollbar.configure(command=_on_yview)
        # The hex pane is the canonical owner of scroll state.
        self._hex_pane.configure(yscrollcommand=_on_scrollbar_set)

        body.rowconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self._status_pane = StatusPane(self)
        self._status_pane.grid(row=2, column=0, sticky="ew")

        self._hex_pane.add_selection_change_listener(self)

        # Ctrl+G keystroke -> jump dialog (upstream KeyStroke binding).
        self.bind_all(
            "<Control-g>", lambda _e: self._show_jump_dialog()
        )

    # ----------------------------------------- SelectionChangeListener

    def selection_changed(self, event: SelectEvent) -> None:
        index = event.get_hex_index()
        nav = event.get_navigation()

        if nav == SelectEvent.NEXT:
            index += 1
        elif nav == SelectEvent.PREVIOUS:
            index -= 1
        elif nav == SelectEvent.UP:
            index -= 16
        elif nav == SelectEvent.DOWN:
            index += 16

        if 0 <= index <= self._model.size() - 1:
            assert self._hex_pane is not None
            assert self._address_pane is not None
            assert self._ascii_pane is not None
            assert self._status_pane is not None
            self._hex_pane.set_selected(index)
            self._address_pane.set_selected(index)
            self._ascii_pane.set_selected(index)
            self._status_pane.update_status(index)
            self._selected_index = index

    # ------------------------------------------------------- jump-to-index

    def _show_jump_dialog(self) -> None:  # pragma: no cover - dialog
        value = simpledialog.askinteger(
            "Jump to index",
            f"Present index: {self._selected_index}\nIndex to go:",
            parent=self,
            minvalue=0,
            maxvalue=max(self._model.size() - 1, 0),
        )
        if value is not None:
            self.selection_changed(SelectEvent(value, SelectEvent.IN))

    # ------------------------------------------------------------- testing

    def get_hex_pane(self) -> HexPane | None:
        return self._hex_pane

    def get_address_pane(self) -> AddressPane | None:
        return self._address_pane

    def get_ascii_pane(self) -> ASCIIPane | None:
        return self._ascii_pane

    def get_status_pane(self) -> StatusPane | None:
        return self._status_pane

    def get_selected_index(self) -> int:
        return self._selected_index
