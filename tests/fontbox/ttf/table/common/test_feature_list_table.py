"""Tests for :class:`FeatureListTable`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub.feature_record import FeatureRecord
from pypdfbox.fontbox.ttf.gsub.feature_table import FeatureTable
from pypdfbox.fontbox.ttf.table.common.feature_list_table import FeatureListTable


def _record(tag: str) -> FeatureRecord:
    return FeatureRecord(feature_tag=tag, feature_table=FeatureTable())


def test_count_and_records_stored() -> None:
    records = (_record("liga"), _record("kern"))
    table = FeatureListTable(2, records)
    assert table.get_feature_count() == 2
    assert table.get_feature_records() == records


def test_records_returned_as_tuple() -> None:
    table = FeatureListTable(1, [_record("liga")])
    assert isinstance(table.get_feature_records(), tuple)


def test_to_string_matches_upstream_format() -> None:
    table = FeatureListTable(3, ())
    assert table.to_string() == "FeatureListTable[featureCount=3]"
    assert str(table) == "FeatureListTable[featureCount=3]"


def test_feature_count_independent_of_records_length() -> None:
    # Upstream stores featureCount independently — we keep that
    # behaviour so round-trip tooling can detect malformed tables.
    table = FeatureListTable(99, ())
    assert table.get_feature_count() == 99
    assert table.get_feature_records() == ()


def test_records_immutable_after_construction() -> None:
    src = [_record("liga"), _record("kern")]
    table = FeatureListTable(2, src)
    src.append(_record("salt"))
    assert len(table.get_feature_records()) == 2
