"""Tests for :class:`LookupListTable`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub.lookup_table import LookupTable
from pypdfbox.fontbox.ttf.table.common.lookup_list_table import LookupListTable


def test_count_and_lookups_stored() -> None:
    lookups = (LookupTable(lookup_type=1), LookupTable(lookup_type=4))
    table = LookupListTable(2, lookups)
    assert table.get_lookup_count() == 2
    assert table.get_lookups() == lookups


def test_lookups_returned_as_tuple() -> None:
    table = LookupListTable(1, [LookupTable()])
    assert isinstance(table.get_lookups(), tuple)


def test_to_string_matches_upstream_format() -> None:
    table = LookupListTable(5, ())
    assert table.to_string() == "LookupListTable[lookupCount=5]"
    assert str(table) == "LookupListTable[lookupCount=5]"


def test_lookup_count_independent_of_lookups_length() -> None:
    table = LookupListTable(7, ())
    assert table.get_lookup_count() == 7
    assert table.get_lookups() == ()


def test_lookups_immutable_after_construction() -> None:
    src = [LookupTable(lookup_type=1)]
    table = LookupListTable(1, src)
    src.append(LookupTable(lookup_type=2))
    assert len(table.get_lookups()) == 1
