"""Tests for :class:`CoverageTableFormat1`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.table.common.coverage_table_format1 import (
    CoverageTable,
    CoverageTableFormat1,
)


def test_format_byte_stored_on_base() -> None:
    table = CoverageTableFormat1(1, [10, 20, 30])
    assert table.get_coverage_format() == 1
    # Format 1 stores the format byte on CoverageTable; the field is
    # accessible the same way for both subclasses.
    assert isinstance(table, CoverageTable)


def test_get_size_returns_array_length() -> None:
    assert CoverageTableFormat1(1, []).get_size() == 0
    assert CoverageTableFormat1(1, [42]).get_size() == 1
    assert CoverageTableFormat1(1, [1, 2, 3, 4, 5]).get_size() == 5


def test_get_glyph_id_returns_array_entry() -> None:
    table = CoverageTableFormat1(1, [10, 20, 30])
    assert table.get_glyph_id(0) == 10
    assert table.get_glyph_id(1) == 20
    assert table.get_glyph_id(2) == 30


def test_get_glyph_id_out_of_range_raises() -> None:
    table = CoverageTableFormat1(1, [10, 20, 30])
    with pytest.raises(IndexError):
        table.get_glyph_id(3)


def test_coverage_index_hit_returns_array_index() -> None:
    table = CoverageTableFormat1(1, [10, 20, 30, 40])
    assert table.get_coverage_index(10) == 0
    assert table.get_coverage_index(20) == 1
    assert table.get_coverage_index(30) == 2
    assert table.get_coverage_index(40) == 3


def test_coverage_index_miss_returns_java_style_negative() -> None:
    table = CoverageTableFormat1(1, [10, 20, 30])
    # -insertionPoint - 1: 5 inserts at 0 → -1; 15 inserts at 1 → -2;
    # 25 inserts at 2 → -3; 35 inserts at 3 → -4.
    assert table.get_coverage_index(5) == -1
    assert table.get_coverage_index(15) == -2
    assert table.get_coverage_index(25) == -3
    assert table.get_coverage_index(35) == -4


def test_get_glyph_array_is_immutable_tuple() -> None:
    arr = [1, 2, 3]
    table = CoverageTableFormat1(1, arr)
    out = table.get_glyph_array()
    assert isinstance(out, tuple)
    assert out == (1, 2, 3)
    # Mutating the source list must not affect the stored coverage.
    arr.append(99)
    assert table.get_glyph_array() == (1, 2, 3)


def test_to_string_matches_java_format() -> None:
    table = CoverageTableFormat1(1, [10, 20, 30])
    assert table.to_string() == "CoverageTableFormat1[coverageFormat=1,glyphArray=[10, 20, 30]]"


def test_empty_array_to_string() -> None:
    table = CoverageTableFormat1(1, [])
    assert table.to_string() == "CoverageTableFormat1[coverageFormat=1,glyphArray=[]]"
