"""Render a float-RGB tuple as a Tkinter swatch.

Ported from ``org.apache.pdfbox.debugger.colorpane.ColorBarCellRenderer``.

Upstream is a ``DefaultTableCellRenderer``-equivalent that paints a
``JLabel`` with an opaque background set to the cell value (a
``java.awt.Color``). In Tkinter ``ttk.Treeview`` doesn't support
per-cell background colors directly, so we ship two facilities:

* :meth:`to_hex` — convert a float-RGB tuple in ``[0, 1]^3`` to a
  Tkinter hex string ``#RRGGBB``. This is what the table-backed views
  use to tag rows.
* :meth:`render_swatch` — build a ``tk.Canvas`` filled with the
  requested color. Useful for any view that wants to drop a swatch
  next to a row (e.g. a separate detail pane).
"""

from __future__ import annotations

import tkinter as tk


class ColorBarCellRenderer:
    """Tkinter-friendly equivalent of upstream's ``TableCellRenderer``.

    Stateless (matches upstream — no fields). Both helpers are
    instance methods so the surface mirrors upstream as closely as
    possible; static-method semantics are still available via the
    class.
    """

    def get_table_cell_renderer_component(
        self,
        master: tk.Misc | None,
        value: tuple[float, float, float] | None,
        _is_selected: bool = False,
        _has_focus: bool = False,
        _row: int = 0,
        _column: int = 0,
    ) -> tk.Canvas:
        """Tkinter analogue of upstream's
        ``getTableCellRendererComponent(JTable, Object, boolean,
        boolean, int, int)``.

        Returns a ``tk.Canvas`` filled with the cell color. The
        boolean / int parameters are accepted but ignored — they
        exist solely to preserve the upstream method shape.
        """
        return self.render_swatch(master, value)

    # ---- Tkinter helpers --------------------------------------------------

    @staticmethod
    def to_hex(color: tuple[float, float, float] | None) -> str:
        """Convert a float-RGB tuple to a ``#RRGGBB`` Tkinter color.

        ``None`` maps to ``#FFFFFF`` (the cell renders as a white
        swatch, matching the default ``JLabel`` background upstream
        would show for a null color). Out-of-range channel values are
        clamped to ``[0, 1]`` before quantisation.
        """
        if color is None:
            return "#FFFFFF"
        r, g, b = color
        r_int = max(0, min(255, int(round(r * 255))))
        g_int = max(0, min(255, int(round(g * 255))))
        b_int = max(0, min(255, int(round(b * 255))))
        return f"#{r_int:02X}{g_int:02X}{b_int:02X}"

    def render_swatch(
        self,
        master: tk.Misc | None,
        color: tuple[float, float, float] | None,
        width: int = 60,
        height: int = 20,
    ) -> tk.Canvas:
        """Return a ``tk.Canvas`` filled with ``color``.

        The default dimensions match upstream's row heights (60x for
        DeviceN, 40x for Indexed — caller can override).
        """
        canvas = tk.Canvas(
            master, width=width, height=height, highlightthickness=0
        )
        canvas.configure(background=self.to_hex(color))
        return canvas
