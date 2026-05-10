"""Tests for :class:`pypdfbox.fontbox.ttf.table.common.range_record.RangeRecord`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.table.common.range_record import RangeRecord


def test_default_constructor_zero_filled() -> None:
    record = RangeRecord()
    assert record.get_start_glyph_id() == 0
    assert record.get_end_glyph_id() == 0
    assert record.get_start_coverage_index() == 0


def test_accessors_match_constructor_args() -> None:
    record = RangeRecord(10, 25, 7)
    assert record.get_start_glyph_id() == 10
    assert record.get_end_glyph_id() == 25
    assert record.get_start_coverage_index() == 7


def test_to_string_matches_upstream_format() -> None:
    record = RangeRecord(5, 9, 3)
    expected = "RangeRecord[startGlyphID=5,endGlyphID=9,startCoverageIndex=3]"
    assert record.to_string() == expected
    assert str(record) == expected


def test_record_is_frozen() -> None:
    import dataclasses

    record = RangeRecord(1, 2, 3)
    try:
        record.start_glyph_id = 9  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("RangeRecord must be frozen")


def test_equality_uses_value_semantics() -> None:
    assert RangeRecord(1, 2, 3) == RangeRecord(1, 2, 3)
    assert RangeRecord(1, 2, 3) != RangeRecord(1, 2, 4)
