"""Tests for :class:`IndexedTableModel`.

Pure-logic tests — no Tk required.
"""

from __future__ import annotations

from pypdfbox.debugger.colorpane.indexed_colorant import IndexedColorant
from pypdfbox.debugger.colorpane.indexed_table_model import IndexedTableModel


def _make(index: int, rgb: list[float]) -> IndexedColorant:
    c = IndexedColorant()
    c.set_index(index)
    c.set_rgb_values(rgb)
    return c


def test_row_and_column_counts() -> None:
    model = IndexedTableModel(
        [_make(0, [0.0, 0.0, 0.0]), _make(1, [1.0, 0.0, 0.0])]
    )
    assert model.get_row_count() == 2
    assert model.get_column_count() == 3


def test_column_names_match_upstream() -> None:
    model = IndexedTableModel([])
    assert model.get_column_name(0) == "Index"
    assert model.get_column_name(1) == "RGB value"
    assert model.get_column_name(2) == "Color"


def test_get_columns_returns_fresh_list() -> None:
    model = IndexedTableModel([])
    cols = model.get_columns()
    cols.append("zzz")
    assert model.get_columns() == ["Index", "RGB value", "Color"]


def test_get_value_at_dispatches_to_colorant_accessors() -> None:
    colorant = _make(7, [1.0, 0.5, 0.0])
    model = IndexedTableModel([colorant])
    assert model.get_value_at(0, 0) == 7
    assert model.get_value_at(0, 1) == "255, 127, 0"
    assert model.get_value_at(0, 2) == (1.0, 0.5, 0.0)
    assert model.get_value_at(0, 99) is None


def test_get_column_class_returns_upstream_tags() -> None:
    model = IndexedTableModel([])
    assert model.get_column_class(0) == "Integer"
    assert model.get_column_class(1) == "String"
    assert model.get_column_class(2) == "Color"
    assert model.get_column_class(99) is None


def test_get_rows_round_trips_all_cells() -> None:
    a = _make(0, [0.0, 0.0, 0.0])
    b = _make(1, [1.0, 0.0, 0.0])
    model = IndexedTableModel([a, b])
    rows = model.get_rows()
    assert rows == [
        [0, "0, 0, 0", (0.0, 0.0, 0.0)],
        [1, "255, 0, 0", (1.0, 0.0, 0.0)],
    ]
