"""Tkinter widget that renders a ``Flag`` table.

Tkinter port of ``org.apache.pdfbox.debugger.flagbitspane.FlagBitsPaneView``.

The Swing original used ``JPanel`` + ``GridBagLayout`` + ``JTable``; this
port uses ``ttk.Frame`` + ``ttk.Treeview`` with one column per column name
returned by the flag. The header ``JLabel`` (monospaced bold) becomes a
``ttk.Label`` with a fixed-width font.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Sequence
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any


class FlagBitsPaneView(ttk.Frame):
    """Tkinter frame showing one ``Flag`` decoded into a treeview."""

    def __init__(
        self,
        master: tk.Misc | None,
        flag_header: str,
        flag_value: str | None,
        table_row_data: Sequence[Sequence[Any]] | None,
        column_names: Sequence[str],
    ) -> None:
        """Build the view.

        :param master: parent widget (may be ``None`` for a top-level Tk root).
        :param flag_header: large header text (e.g. ``"Annot flag"``).
        :param flag_value: line shown below the header (the raw ``Flag value: …``
            string). When ``None`` or *table_row_data* is ``None`` the view
            renders empty — matching upstream's behaviour when ``FlagBitsPane``
            is asked for an unknown flag type.
        :param table_row_data: 2-d sequence of row data.
        :param column_names: sequence of column titles. Length must match the
            width of every row in *table_row_data*.
        """
        super().__init__(master)

        self._flag_header = flag_header
        self._flag_value = flag_value
        self._table_data: list[list[Any]] = (
            [list(row) for row in table_row_data]
            if table_row_data is not None
            else []
        )
        self._column_names: list[str] = list(column_names)
        self._tree: ttk.Treeview | None = None

        if flag_value is not None and table_row_data is not None:
            self.create_view()

    # ---- public accessors --------------------------------------------------

    def get_panel(self) -> FlagBitsPaneView:
        """Return this frame.

        Upstream returns the contained ``JPanel`` from ``getPanel()`` —
        ``FlagBitsPaneView`` itself is the frame here, so we just return
        ``self``.
        """
        return self

    @property
    def tree(self) -> ttk.Treeview | None:
        """The underlying ``ttk.Treeview`` (``None`` until populated)."""
        return self._tree

    # ---- view assembly -----------------------------------------------------

    def create_view(self) -> None:
        """Build the header / value labels and the flag-bits ``Treeview``.

        Mirrors upstream private ``FlagBitsPaneView.createView()``. Public
        on the Python port for parity tooling.
        """
        # Mimic the Swing preferred-size 300x500 with a request hint.
        # configure() may fail in headless test environments — ignore.
        with contextlib.suppress(tk.TclError):
            self.configure(width=300, height=500)

        header_font = tkfont.Font(family="Courier", size=30, weight=tkfont.BOLD)
        value_font = tkfont.Font(family="Courier", size=20, weight=tkfont.BOLD)

        ttk.Label(self, text=self._flag_header, font=header_font).pack(
            anchor="w", padx=4, pady=(4, 0)
        )
        ttk.Label(self, text=self._flag_value or "", font=value_font).pack(
            anchor="w", padx=4
        )

        # Use the first column as the treeview's #0 column so it carries
        # the row text directly (handles arbitrary row widths).
        first_name, *rest = self._column_names
        tree = ttk.Treeview(self, columns=rest, show="tree headings")
        tree.heading("#0", text=first_name)
        for name in rest:
            tree.heading(name, text=name)
            tree.column(name, anchor="w")
        tree.column("#0", anchor="w")
        for row in self._table_data:
            head, *tail = row
            tree.insert(
                "", "end", text=str(head), values=[str(v) for v in tail]
            )
        tree.pack(fill="both", expand=True, padx=4, pady=4)

        self._tree = tree

    # Back-compat private alias.
    _create_view = create_view
