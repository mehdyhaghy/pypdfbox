"""Table model for the DeviceN color-space inspector.

Ported from ``org.apache.pdfbox.debugger.colorpane.DeviceNTableModel``.

Upstream extends Swing's ``AbstractTableModel`` to drive a ``JTable``.
In the Tkinter port we back a ``ttk.Treeview`` with a plain helper
class that exposes the same surface the Swing widget consumed —
``get_column_count`` / ``get_row_count`` / ``get_value_at`` /
``get_column_name`` / ``get_column_class`` plus convenience
``get_columns()`` / ``get_rows()`` accessors used by the view code.
"""

from __future__ import annotations

from collections.abc import Sequence

from pypdfbox.debugger.colorpane.device_n_colorant import DeviceNColorant

# The "class" tag returned by ``get_column_class`` for the color
# columns. Upstream returns ``java.awt.Color.class`` — we use the
# string ``"Color"`` so the view code can spot color cells without
# pulling in an AWT-equivalent. Column 0 (colorant name) returns
# ``"String"`` to match upstream's ``String.class``.
_COLOR_CLASS = "Color"
_STRING_CLASS = "String"


class DeviceNTableModel:
    """Thin model class wrapping a list of :class:`DeviceNColorant`."""

    # Upstream private static field ``COLUMNNAMES``.
    _COLUMN_NAMES: tuple[str, ...] = ("Colorant", "Maximum", "Minimum")

    def __init__(self, colorants: Sequence[DeviceNColorant]) -> None:
        # Defensive copy — upstream stores the array reference directly,
        # but the upstream caller never mutates the array after
        # construction so the difference is invisible.
        self._data: list[DeviceNColorant] = list(colorants)

    # ---- AbstractTableModel surface ---------------------------------------

    def get_row_count(self) -> int:
        return len(self._data)

    def get_column_count(self) -> int:
        return len(self._COLUMN_NAMES)

    def get_value_at(self, row: int, column: int) -> object:
        colorant = self._data[row]
        if column == 0:
            return colorant.get_name()
        if column == 1:
            return colorant.get_maximum()
        if column == 2:
            return colorant.get_minimum()
        return None

    def get_column_name(self, column: int) -> str:
        return self._COLUMN_NAMES[column]

    def get_column_class(self, column_index: int) -> str | None:
        if column_index == 0:
            return _STRING_CLASS
        if column_index in (1, 2):
            return _COLOR_CLASS
        return None

    # ---- Tkinter-friendly helpers -----------------------------------------

    def get_columns(self) -> list[str]:
        """Return the column titles as a fresh list."""
        return list(self._COLUMN_NAMES)

    def get_rows(self) -> list[list[object]]:
        """Return every row as a list of column values.

        Equivalent to iterating ``get_value_at(row, col)`` for every
        cell. Used by the Tkinter view to populate a ``ttk.Treeview``
        in one shot.
        """
        rows: list[list[object]] = []
        for row in range(self.get_row_count()):
            rows.append(
                [self.get_value_at(row, col) for col in range(self.get_column_count())]
            )
        return rows
