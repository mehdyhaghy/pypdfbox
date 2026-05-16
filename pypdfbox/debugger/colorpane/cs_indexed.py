"""Indexed color-space inspector.

Ported from ``org.apache.pdfbox.debugger.colorpane.CSIndexed``.

Renders a header label, a total-count label and a ``ttk.Treeview``
driven by :class:`IndexedTableModel`. Each row gets a tag whose
background matches the indexed entry's color so the swatch column is
visible — mirrors upstream's ``ColorBarCellRenderer``.

Swing → Tkinter mapping:
* ``JPanel`` + ``GridBagLayout`` / ``BoxLayout`` → ``ttk.Frame`` with
  packed children.
* ``JTable`` → ``ttk.Treeview``.
* ``JScrollPane`` → ``ttk.Scrollbar`` wired into the treeview.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from pypdfbox.cos import COSArray, COSNumber
from pypdfbox.debugger.colorpane.color_bar_cell_renderer import (
    ColorBarCellRenderer,
)
from pypdfbox.debugger.colorpane.indexed_colorant import IndexedColorant
from pypdfbox.debugger.colorpane.indexed_table_model import IndexedTableModel
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed


class CSIndexed:
    """Tkinter inspector for a ``/Indexed`` color space."""

    def __init__(
        self, array: COSArray, master: tk.Misc | None = None
    ) -> None:
        """Build the pane.

        :param array: COSArray for the Indexed color space — shape
            ``[/Indexed <base> <hival> <lookup>]``.
        :param master: parent Tk widget. ``None`` falls back to the
            implicit default root.

        :raises OSError: when the underlying ``PDIndexed`` instance
            cannot be created (mirrors upstream's ``throws IOException``).
        """
        self._indexed = PDIndexed(array)
        self._color_count = self.get_hival(array) + 1
        self._panel: ttk.Frame | None = None
        colorants = self.get_colorant_data()
        self._table_model = IndexedTableModel(colorants)
        self._tree: ttk.Treeview | None = None
        self.init_ui(master, colorants)

    # ---- data extraction --------------------------------------------------

    def get_colorant_data(self) -> list[IndexedColorant]:
        """Build one :class:`IndexedColorant` per palette entry.

        Mirrors upstream ``CSIndexed.getColorantData()`` — for every
        index 0..colorCount-1, call ``indexed.toRGB(new float[]{i})``
        and stash the three floats in the colorant record.
        """
        colorants: list[IndexedColorant] = []
        for i in range(self._color_count):
            colorant = IndexedColorant()
            colorant.set_index(i)
            rgb_values = self._indexed.to_rgb([float(i)])
            colorant.set_rgb_values(rgb_values)
            colorants.append(colorant)
        return colorants

    @staticmethod
    def get_hival(array: COSArray) -> int:
        """Read the ``/Indexed`` array's hival entry.

        Mirrors upstream ``getHival(COSArray)`` — clamps to 255.
        """
        entry = array.get_object(2).get_cos_object()
        if not isinstance(entry, COSNumber):
            raise TypeError(
                "Indexed color space hival must be a COSNumber, got "
                f"{type(entry).__name__}"
            )
        return min(entry.int_value(), 255)

    # ---- UI ---------------------------------------------------------------

    def init_ui(
        self, master: tk.Misc | None, colorants: list[IndexedColorant]
    ) -> None:
        panel = ttk.Frame(master)
        with contextlib.suppress(tk.TclError):
            panel.configure(width=300, height=500)
        self._panel = panel

        header_font = tkfont.Font(family="Courier", size=30, weight=tkfont.BOLD)
        count_font = tkfont.Font(family="Courier", size=20, weight=tkfont.BOLD)

        ttk.Label(
            panel, text="Indexed colorspace", font=header_font
        ).pack(anchor="w", padx=4, pady=(4, 0))

        ttk.Label(
            panel,
            text=f" Total Color Count: {self._color_count}",
            font=count_font,
        ).pack(anchor="w", padx=4)

        columns = self._table_model.get_columns()
        first, *rest = columns
        tree = ttk.Treeview(panel, columns=rest, show="tree headings")
        tree.heading("#0", text=first)
        # Upstream forces column widths — preserve as best-effort.
        tree.column("#0", minwidth=30, width=50, anchor="w")
        for col in rest:
            tree.heading(col, text=col)
            if col == "RGB value":
                tree.column(col, minwidth=100, width=100, anchor="w")
            else:
                tree.column(col, anchor="w")

        renderer = ColorBarCellRenderer()
        # Approximate upstream's ``setRowHeight(40)``.
        with contextlib.suppress(tk.TclError):
            style = ttk.Style(panel)
            style.configure("CSIndexed.Treeview", rowheight=40)
            tree.configure(style="CSIndexed.Treeview")

        for colorant in colorants:
            index = colorant.get_index()
            rgb_string = colorant.get_rgb_values_string()
            color = colorant.get_color()
            color_hex = renderer.to_hex(color)
            tag = f"csidx-{index}"
            tree.insert(
                "",
                "end",
                text=str(index),
                values=(rgb_string, color_hex),
                tags=(tag,),
            )
            with contextlib.suppress(tk.TclError):
                tree.tag_configure(tag, background=color_hex)

        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scrollbar.pack(side="right", fill="y", pady=4)

        self._tree = tree

    # ---- public surface ---------------------------------------------------

    def get_panel(self) -> ttk.Frame | None:
        """Return the main panel. Mirrors upstream ``CSIndexed.getPanel()``."""
        return self._panel

    @property
    def color_count(self) -> int:
        """Total colors in the palette (``hival`` + 1, clamped at 256)."""
        return self._color_count

    @property
    def tree(self) -> ttk.Treeview | None:
        """The underlying ``ttk.Treeview`` (``None`` before init)."""
        return self._tree

    @property
    def table_model(self) -> IndexedTableModel:
        """The :class:`IndexedTableModel` backing the treeview."""
        return self._table_model

    # ---- back-compat aliases --------------------------------------------
    # Earlier revisions exposed these as ``_``-prefixed private helpers.
    # The names were promoted in wave 1311 to mirror upstream's accessors;
    # keep the aliases live so existing callers continue to resolve.
    _get_colorant_data = get_colorant_data
    _get_hival = get_hival
    _init_ui = init_ui
