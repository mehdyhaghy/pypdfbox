"""Table model for the Indexed color-space inspector.

Ported from ``org.apache.pdfbox.debugger.colorpane.IndexedTableModel``.

Same pattern as :class:`DeviceNTableModel` — exposes upstream's
``AbstractTableModel`` surface plus convenience helpers used by the
Tkinter view.
"""

from __future__ import annotations

from collections.abc import Sequence

from pypdfbox.debugger.colorpane.indexed_colorant import IndexedColorant

# Class tags returned by ``get_column_class``. Upstream returns
# ``Integer.class`` / ``String.class`` / ``Color.class`` — we use
# string tags so the view code can dispatch without an AWT import.
_INTEGER_CLASS = "Integer"
_STRING_CLASS = "String"
_COLOR_CLASS = "Color"


class IndexedTableModel:
    """Thin model class wrapping a list of :class:`IndexedColorant`."""

    # Upstream private static field ``COLUMNSNAMES`` (note the typo —
    # preserved on the public surface via ``get_column_name`` /
    # ``get_columns`` outputs but renamed here to keep the Python
    # identifier readable).
    _COLUMN_NAMES: tuple[str, ...] = ("Index", "RGB value", "Color")

    def __init__(self, colorants: Sequence[IndexedColorant]) -> None:
        self._data: list[IndexedColorant] = list(colorants)

    # ---- AbstractTableModel surface ---------------------------------------

    def get_row_count(self) -> int:
        return len(self._data)

    def get_column_count(self) -> int:
        return len(self._COLUMN_NAMES)

    def get_value_at(self, row: int, column: int) -> object:
        colorant = self._data[row]
        if column == 0:
            return colorant.get_index()
        if column == 1:
            return colorant.get_rgb_values_string()
        if column == 2:
            return colorant.get_color()
        return None

    def get_column_name(self, column: int) -> str:
        return self._COLUMN_NAMES[column]

    def get_column_class(self, column_index: int) -> str | None:
        if column_index == 0:
            return _INTEGER_CLASS
        if column_index == 1:
            return _STRING_CLASS
        if column_index == 2:
            return _COLOR_CLASS
        return None

    # ---- Tkinter-friendly helpers -----------------------------------------

    def get_columns(self) -> list[str]:
        return list(self._COLUMN_NAMES)

    def get_rows(self) -> list[list[object]]:
        rows: list[list[object]] = []
        for row in range(self.get_row_count()):
            rows.append(
                [self.get_value_at(row, col) for col in range(self.get_column_count())]
            )
        return rows
