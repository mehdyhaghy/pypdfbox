"""Wave 354 robustness tests for :class:`pypdfbox.pdmodel.common.PDMatrix`."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common import PDMatrix


@pytest.mark.parametrize(
    ("row", "column"),
    [(-1, 0), (0, -1), (3, 0), (0, 3)],
)
def test_get_value_rejects_out_of_bounds_index(row: int, column: int) -> None:
    m = PDMatrix()
    with pytest.raises(IndexError, match="range 0..2"):
        m.get_value(row, column)


@pytest.mark.parametrize(
    ("row", "column"),
    [(-1, 0), (0, -1), (3, 0), (0, 3)],
)
def test_set_value_rejects_out_of_bounds_index(row: int, column: int) -> None:
    m = PDMatrix()
    before = m.get_single()
    with pytest.raises(IndexError, match="range 0..2"):
        m.set_value(row, column, 9.0)
    assert m.get_single() == before
