from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import (
    LookupTable,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
)


def test_default_construction() -> None:
    lt = LookupTable()
    assert lt.get_lookup_type() == 0
    assert lt.get_lookup_flag() == 0
    assert lt.get_mark_filtering_set() == 0
    assert lt.get_sub_tables() == ()


def test_round_trip_with_subtables() -> None:
    s1 = LookupTypeSingleSubstFormat1(delta_glyph_id=1, coverage_table=(10,))
    s2 = LookupTypeSingleSubstFormat2(
        coverage_table=(20,), substitute_glyph_ids=(200,)
    )
    lt = LookupTable(
        lookup_type=1,
        lookup_flag=0x0010,  # UseMarkFilteringSet
        mark_filtering_set=2,
        sub_tables=(s1, s2),
    )
    assert lt.get_lookup_type() == 1
    assert lt.get_lookup_flag() == 0x0010
    assert lt.get_mark_filtering_set() == 2
    assert lt.get_sub_tables() == (s1, s2)


def test_lookup_flag_bits() -> None:
    # RightToLeft (0x0001) | IgnoreMarks (0x0008)
    lt = LookupTable(lookup_type=1, lookup_flag=0x0009)
    assert lt.get_lookup_flag() & 0x0001 == 0x0001
    assert lt.get_lookup_flag() & 0x0008 == 0x0008
