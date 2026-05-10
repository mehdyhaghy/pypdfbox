"""Tests for :class:`CoverageTableFormat2`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.table.common.coverage_table_format2 import (
    CoverageTableFormat2,
)
from pypdfbox.fontbox.ttf.table.common.range_record import RangeRecord


def test_glyph_array_built_from_ranges() -> None:
    ranges = (RangeRecord(10, 12, 0), RangeRecord(20, 22, 3))
    table = CoverageTableFormat2(2, ranges)
    assert table.get_glyph_array() == (10, 11, 12, 20, 21, 22)
    assert table.get_size() == 6


def test_inherits_coverage_lookup_semantics() -> None:
    table = CoverageTableFormat2(2, (RangeRecord(10, 12, 0), RangeRecord(20, 22, 3)))
    # Hits land at the flattened index.
    assert table.get_coverage_index(10) == 0
    assert table.get_coverage_index(12) == 2
    assert table.get_coverage_index(20) == 3
    # Misses use Java-style negative encoding.
    assert table.get_coverage_index(15) == -4
    assert table.get_coverage_index(0) == -1


def test_get_range_records_returns_supplied_records() -> None:
    records = (RangeRecord(1, 5, 0), RangeRecord(8, 9, 5))
    table = CoverageTableFormat2(2, records)
    assert table.get_range_records() == records


def test_single_glyph_range() -> None:
    # start == end → exactly one glyph.
    table = CoverageTableFormat2(2, (RangeRecord(42, 42, 0),))
    assert table.get_glyph_array() == (42,)
    assert table.get_coverage_index(42) == 0


def test_to_string_format_matches_upstream() -> None:
    table = CoverageTableFormat2(2, (RangeRecord(1, 3, 0),))
    assert table.to_string() == "CoverageTableFormat2[coverageFormat=2]"


def test_empty_range_list_yields_empty_table() -> None:
    table = CoverageTableFormat2(2, ())
    assert table.get_size() == 0
    assert table.get_glyph_array() == ()
    assert table.get_range_records() == ()
