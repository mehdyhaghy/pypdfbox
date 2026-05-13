"""Tests for :class:`DeviceNTableModel`.

Pure-logic tests — no Tk required.
"""

from __future__ import annotations

from pypdfbox.debugger.colorpane.device_n_colorant import DeviceNColorant
from pypdfbox.debugger.colorpane.device_n_table_model import DeviceNTableModel


def _make(
    name: str,
    mx: tuple[float, float, float],
    mn: tuple[float, float, float],
) -> DeviceNColorant:
    c = DeviceNColorant()
    c.set_name(name)
    c.set_maximum(mx)
    c.set_minimum(mn)
    return c


def test_row_and_column_counts() -> None:
    model = DeviceNTableModel(
        [
            _make("Cyan", (0.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
            _make("Magenta", (1.0, 0.0, 1.0), (1.0, 1.0, 1.0)),
        ]
    )
    assert model.get_row_count() == 2
    assert model.get_column_count() == 3


def test_column_names_match_upstream() -> None:
    model = DeviceNTableModel([])
    assert model.get_column_name(0) == "Colorant"
    assert model.get_column_name(1) == "Maximum"
    assert model.get_column_name(2) == "Minimum"


def test_get_columns_returns_fresh_list() -> None:
    model = DeviceNTableModel([])
    cols_a = model.get_columns()
    cols_b = model.get_columns()
    assert cols_a == cols_b == ["Colorant", "Maximum", "Minimum"]
    cols_a.append("zzz")
    assert model.get_columns() == ["Colorant", "Maximum", "Minimum"]


def test_get_value_at_dispatches_to_colorant_accessors() -> None:
    colorant = _make("Cyan", (0.0, 1.0, 1.0), (1.0, 1.0, 1.0))
    model = DeviceNTableModel([colorant])
    assert model.get_value_at(0, 0) == "Cyan"
    assert model.get_value_at(0, 1) == (0.0, 1.0, 1.0)
    assert model.get_value_at(0, 2) == (1.0, 1.0, 1.0)
    assert model.get_value_at(0, 99) is None


def test_get_column_class_returns_upstream_tags() -> None:
    model = DeviceNTableModel([])
    assert model.get_column_class(0) == "String"
    assert model.get_column_class(1) == "Color"
    assert model.get_column_class(2) == "Color"
    assert model.get_column_class(99) is None


def test_get_rows_round_trips_all_cells() -> None:
    a = _make("Cyan", (0.0, 1.0, 1.0), (1.0, 1.0, 1.0))
    b = _make("Magenta", (1.0, 0.0, 1.0), (1.0, 1.0, 1.0))
    model = DeviceNTableModel([a, b])
    rows = model.get_rows()
    assert rows == [
        ["Cyan", (0.0, 1.0, 1.0), (1.0, 1.0, 1.0)],
        ["Magenta", (1.0, 0.0, 1.0), (1.0, 1.0, 1.0)],
    ]
