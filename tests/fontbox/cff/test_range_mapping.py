"""Hand-written tests for :class:`RangeMapping`."""

from __future__ import annotations

from pypdfbox.fontbox.cff import RangeMapping


def test_range_endpoints() -> None:
    mapping = RangeMapping(start_gid=10, first=100, n_left=4)
    # 5 glyphs total: GID 10..14 -> SID/CID 100..104.
    assert mapping.start_value == 10
    assert mapping.end_value == 14
    assert mapping.start_mapped_value == 100
    assert mapping.end_mapped_value == 104


def test_is_in_range_inclusive() -> None:
    mapping = RangeMapping(start_gid=10, first=100, n_left=4)
    assert mapping.is_in_range(10) is True
    assert mapping.is_in_range(14) is True
    assert mapping.is_in_range(15) is False
    assert mapping.is_in_range(9) is False


def test_is_in_reverse_range_inclusive() -> None:
    mapping = RangeMapping(start_gid=10, first=100, n_left=4)
    assert mapping.is_in_reverse_range(100) is True
    assert mapping.is_in_reverse_range(104) is True
    assert mapping.is_in_reverse_range(105) is False
    assert mapping.is_in_reverse_range(99) is False


def test_map_value_in_range() -> None:
    mapping = RangeMapping(start_gid=10, first=100, n_left=4)
    assert mapping.map_value(10) == 100
    assert mapping.map_value(12) == 102
    assert mapping.map_value(14) == 104


def test_map_value_out_of_range_returns_zero() -> None:
    mapping = RangeMapping(start_gid=10, first=100, n_left=4)
    assert mapping.map_value(9) == 0
    assert mapping.map_value(15) == 0


def test_map_reverse_value() -> None:
    mapping = RangeMapping(start_gid=10, first=100, n_left=4)
    assert mapping.map_reverse_value(100) == 10
    assert mapping.map_reverse_value(104) == 14
    assert mapping.map_reverse_value(99) == 0
    assert mapping.map_reverse_value(105) == 0


def test_single_glyph_range() -> None:
    mapping = RangeMapping(start_gid=7, first=21, n_left=0)
    assert mapping.is_in_range(7) is True
    assert mapping.is_in_range(8) is False
    assert mapping.map_value(7) == 21
    assert mapping.map_reverse_value(21) == 7


def test_to_string_matches_upstream_format() -> None:
    # Upstream toString (CFFParser.java:1703-1707):
    # ``getClass().getName() + "[start value=" + startValue
    #   + ", end value=" + endValue + ", start mapped-value=" +
    #   startMappedValue + ", end mapped-value=" + endMappedValue + "]"``.
    mapping = RangeMapping(start_gid=10, first=100, n_left=4)
    rendered = mapping.to_string()
    assert "RangeMapping" in rendered
    assert "[start value=10, " in rendered
    assert "end value=14, " in rendered
    assert "start mapped-value=100, " in rendered
    assert "end mapped-value=104]" in rendered
    assert str(mapping) == rendered
