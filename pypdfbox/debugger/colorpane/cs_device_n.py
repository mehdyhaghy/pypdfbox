"""DeviceN color-space inspector.

Ported from ``org.apache.pdfbox.debugger.colorpane.CSDeviceN``.

Renders a header label plus a ``ttk.Treeview`` driven by
:class:`DeviceNTableModel`. The two color columns are coloured by
attaching a per-row ``ttk.Style``-managed tag whose background comes
from :meth:`ColorBarCellRenderer.to_hex`.

Swing → Tkinter mapping:
* ``JPanel`` + ``BoxLayout.Y_AXIS`` → ``ttk.Frame`` with packed children.
* ``JTable`` + ``setDefaultRenderer(Color.class, ColorBarCellRenderer)``
  → ``ttk.Treeview`` with one tag per swatch color, each tag styled
  with that color as ``background``.
* ``JScrollPane`` → ``ttk.Scrollbar`` wired into the treeview.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from pypdfbox.cos import COSArray
from pypdfbox.debugger.colorpane.color_bar_cell_renderer import (
    ColorBarCellRenderer,
)
from pypdfbox.debugger.colorpane.device_n_colorant import DeviceNColorant
from pypdfbox.debugger.colorpane.device_n_table_model import DeviceNTableModel
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN


class CSDeviceN:
    """Tkinter inspector for a ``/DeviceN`` color space."""

    def __init__(
        self, array: COSArray, master: tk.Misc | None = None
    ) -> None:
        """Build the pane.

        :param array: COSArray for the DeviceN color space.
        :param master: parent Tk widget. ``None`` falls back to the
            implicit default root.

        :raises OSError: when the DeviceN instance cannot be created
            (mirrors upstream's ``throws IOException``).
        """
        self._device_n = PDDeviceN(array)
        self._panel: ttk.Frame | None = None
        colorants = self.get_colorant_data()
        self._table_model = DeviceNTableModel(colorants)
        self._tree: ttk.Treeview | None = None
        self.init_ui(master, colorants)

    # ---- data extraction --------------------------------------------------

    def get_colorant_data(self) -> list[DeviceNColorant]:
        """Parse colorant data from the wrapped DeviceN color space.

        Mirrors upstream ``CSDeviceN.getColorantData()`` — for every
        colorant we build a unit-vector that lights only that
        colorant, convert it to RGB twice (with the colorant at 1.0
        and at 0.0), and stash the two resulting colors as the
        "maximum"/"minimum" swatches.
        """
        colorant_names = self._device_n.get_colorant_names()
        component_count = len(colorant_names)
        colorants: list[DeviceNColorant] = []
        for i in range(component_count):
            colorant = DeviceNColorant()
            colorant.set_name(colorant_names[i])
            maximum = [0.0] * component_count
            minimum = [0.0] * component_count
            maximum[i] = 1.0
            colorant.set_maximum(self.get_color_obj(self._device_n.to_rgb(maximum)))
            colorant.set_minimum(self.get_color_obj(self._device_n.to_rgb(minimum)))
            colorants.append(colorant)
        return colorants

    @staticmethod
    def get_color_obj(
        rgb_values: list[float] | tuple[float, ...] | None,
    ) -> tuple[float, float, float]:
        """Wrap an ``[r, g, b]`` float list as a 3-tuple.

        Mirrors upstream's private ``getColorObj`` helper which built a
        ``java.awt.Color(float, float, float)``. ``None`` (returned by
        :meth:`PDDeviceN.to_rgb` when no alternate / tint transform is
        available) collapses to opaque black — upstream would have NPE'd
        in this branch; we degrade gracefully instead.
        """
        if rgb_values is None:
            return (0.0, 0.0, 0.0)
        return (rgb_values[0], rgb_values[1], rgb_values[2])

    # ---- UI ---------------------------------------------------------------

    def init_ui(
        self, master: tk.Misc | None, colorants: list[DeviceNColorant]
    ) -> None:
        panel = ttk.Frame(master)
        with contextlib.suppress(tk.TclError):
            panel.configure(width=300, height=500)
        self._panel = panel

        header_font = tkfont.Font(family="Courier", size=30, weight=tkfont.BOLD)
        ttk.Label(
            panel, text="DeviceN colorspace", font=header_font
        ).pack(anchor="center", padx=4, pady=(4, 0))

        columns = self._table_model.get_columns()
        first, *rest = columns
        tree = ttk.Treeview(panel, columns=rest, show="tree headings")
        tree.heading("#0", text=first)
        tree.column("#0", anchor="w")
        for col in rest:
            tree.heading(col, text=col)
            tree.column(col, anchor="w")

        renderer = ColorBarCellRenderer()
        # Approximate upstream's setRowHeight(60) — ttk styles ``Treeview``
        # row height per-instance via a dedicated style name. Failures are
        # ignored so headless tests still work.
        with contextlib.suppress(tk.TclError):
            style = ttk.Style(panel)
            style.configure("CSDeviceN.Treeview", rowheight=60)
            tree.configure(style="CSDeviceN.Treeview")

        for index, colorant in enumerate(colorants):
            name = colorant.get_name() or ""
            max_color = renderer.to_hex(colorant.get_maximum())
            min_color = renderer.to_hex(colorant.get_minimum())
            tag_max = f"csdn-max-{index}"
            tag_min = f"csdn-min-{index}"
            # Tag a row twice — once with each color tag. ttk Treeview
            # only paints with the *last* matching tag's background, so
            # we get a single solid color per row (mirrors upstream
            # JTable's per-cell color but at row resolution).
            tree.insert(
                "",
                "end",
                text=name,
                values=(max_color, min_color),
                tags=(tag_max, tag_min),
            )
            with contextlib.suppress(tk.TclError):
                tree.tag_configure(tag_max, background=max_color)
                tree.tag_configure(tag_min, background=min_color)

        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scrollbar.pack(side="right", fill="y", pady=4)

        self._tree = tree

    # ---- public surface ---------------------------------------------------

    def get_panel(self) -> ttk.Frame | None:
        """Return the main panel. Mirrors upstream ``CSDeviceN.getPanel()``."""
        return self._panel

    @property
    def tree(self) -> ttk.Treeview | None:
        """The underlying ``ttk.Treeview`` (``None`` before init)."""
        return self._tree

    @property
    def table_model(self) -> DeviceNTableModel:
        """The :class:`DeviceNTableModel` backing the treeview."""
        return self._table_model

    # ---- back-compat aliases --------------------------------------------
    # Earlier revisions exposed these as ``_``-prefixed private helpers.
    # The names were promoted in wave 1311 to mirror upstream's accessors;
    # keep the aliases live so existing callers continue to resolve.
    _get_colorant_data = get_colorant_data
    _get_color_obj = get_color_obj
    _init_ui = init_ui
