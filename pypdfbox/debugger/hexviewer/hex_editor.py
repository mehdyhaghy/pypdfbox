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
        self._scroll_pane: ttk.Frame | None = None

        self.create_view()

    # ----------------------------------------------------------- creation

    def create_view(self) -> None:
        """Build the full widget hierarchy.

        Mirrors upstream ``createView()``: upper pane on row 0, the
        scrollable hex/address/ASCII triple on row 1 (returned by
        :meth:`get_scroll_pane`), status pane on row 2, and a ``Ctrl+G``
        accelerator that invokes :meth:`create_jump_dialog`.
        """

        upper_pane = UpperPane(self)
        upper_pane.grid(row=0, column=0, sticky="ew")

        # Scrollable middle row hosting the three column panes.
        body = self.get_scroll_pane()
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
            assert self._address_pane is not None
            assert self._hex_pane is not None
            assert self._ascii_pane is not None
            self._address_pane.yview(*args)
            self._hex_pane.yview(*args)
            self._ascii_pane.yview(*args)

        def _on_scrollbar_set(first: str, last: str) -> None:
            assert self._address_pane is not None
            assert self._ascii_pane is not None
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

    # Backwards-compatible private alias — earlier waves landed the
    # private spelling; keep it so existing call-sites keep working until
    # they migrate to the upstream-aligned public name.
    _create_view = create_view

    def get_scroll_pane(self) -> ttk.Frame:
        """Return the container that scrolls the three column panes.

        Mirrors upstream ``getScrollPane()`` which builds a
        ``JScrollPane`` for the column panel. Tkinter has no built-in
        scroll-pane widget, so the equivalent is a plain ``ttk.Frame``
        coupled to a sibling ``ttk.Scrollbar`` (wired in
        :meth:`create_view`). The frame is created lazily on first call
        and cached so successive callers receive the same instance —
        upstream behaviour, where ``getScrollPane`` is invoked once from
        ``createView``.
        """

        if self._scroll_pane is None:
            self._scroll_pane = ttk.Frame(self)
        return self._scroll_pane

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

    def create_jump_dialog(self) -> tk.Toplevel:
        """Build the modal "Jump to index" dialog.

        Mirrors upstream ``createJumpDialog()`` — a top-level window with
        a ``Present index`` label, an ``Index to go`` entry, and an OK
        button that parses the entry, dispatches a
        ``SelectEvent(index, IN)`` to :meth:`selection_changed` when the
        value is in range, then destroys the dialog.

        Two intentional deviations from upstream:

        * The entry uses a plain ``ttk.Entry`` instead of Swing's
          ``JFormattedTextField(NumberFormat.getIntegerInstance())``
          because Tkinter has no formatted-field analogue. We accept
          ``0x``/``0X``-prefixed hexadecimal in addition to decimal so
          callers can paste byte offsets directly from the hex pane —
          a strict superset of upstream input.
        * An explicit ``OK`` button replaces the Swing ``ActionListener``
          on the entry (which fires on Enter). The Enter key is also
          bound to the same callback, preserving the upstream UX.
        """

        dialog = tk.Toplevel(self)
        dialog.title("Jump to index")
        dialog.transient(self.winfo_toplevel())

        now_label = ttk.Label(
            dialog, text=f"Present index: {self._selected_index}"
        )
        now_label.pack(anchor="w", padx=8, pady=(8, 0))

        input_row = ttk.Frame(dialog)
        input_row.pack(anchor="w", padx=8, pady=8)
        ttk.Label(input_row, text="Index to go:").pack(side="left")
        entry = ttk.Entry(input_row, width=14)
        entry.pack(side="left", padx=(4, 0))

        def _commit(_event: object = None) -> None:
            text = entry.get().strip()
            if not text:
                return
            try:
                index = (
                    int(text, 16)
                    if text.lower().startswith("0x")
                    else int(text, 10)
                )
            except ValueError:
                return
            if 0 <= index <= self._model.size() - 1:
                self.selection_changed(SelectEvent(index, SelectEvent.IN))
                dialog.destroy()

        ok_button = ttk.Button(input_row, text="OK", command=_commit)
        ok_button.pack(side="left", padx=(4, 0))
        entry.bind("<Return>", _commit)

        # Expose internals to test code without leaking back to callers.
        dialog._pypdfbox_entry = entry  # type: ignore[attr-defined]
        dialog._pypdfbox_ok = ok_button  # type: ignore[attr-defined]
        dialog._pypdfbox_commit = _commit  # type: ignore[attr-defined]

        return dialog

    def action_performed(self, event: object | None = None) -> None:  # noqa: ARG002
        """Trigger the jump-to-index dialog from a menu / accelerator action.

        Mirrors the three anonymous ``ActionListener.actionPerformed``
        bodies upstream uses for (a) the OK button in the jump dialog,
        (b) the document-mutation actions, and (c) the ``Ctrl+G`` key
        binding — all three ultimately open / commit the jump dialog.
        The Tkinter port routes a high-level public entry through
        :meth:`_show_jump_dialog`; the event argument is accepted for
        upstream signature parity but unused.
        """
        self._show_jump_dialog()

    def _show_jump_dialog(self) -> None:  # pragma: no cover - dialog
        # Preserved for the Ctrl+G accelerator path. The upstream Swing
        # action calls ``createJumpDialog().setVisible(true)``; we use
        # the simpledialog convenience here because it auto-centres on
        # the parent and blocks correctly without a tk event loop.
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
