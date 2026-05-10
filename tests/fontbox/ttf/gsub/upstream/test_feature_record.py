"""Upstream-shaped tests for ``FeatureRecord``.

There is no standalone ``FeatureRecordTest`` upstream — the record is
exercised through ``GlyphSubstitutionDataExtractorTest`` and the
``GsubWorker*`` tests. These tests capture the constructor / accessor /
``toString`` invariants of
``org.apache.fontbox.ttf.table.common.FeatureRecord``.

Upstream Java reference:
- fontbox/src/main/java/org/apache/fontbox/ttf/table/common/FeatureRecord.java
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import FeatureRecord, FeatureTable


def test_constructor_round_trip() -> None:
    # Java: new FeatureRecord("liga", new FeatureTable(0, 0, new int[0]));
    table = FeatureTable(feature_params=0, lookup_list_indices=())
    fr = FeatureRecord(feature_tag="liga", feature_table=table)
    assert fr.get_feature_tag() == "liga"
    assert fr.get_feature_table() is table


def test_to_string_mirrors_java_format() -> None:
    # Java: String.format("FeatureRecord[featureTag=%s]", featureTag);
    fr = FeatureRecord(feature_tag="liga", feature_table=FeatureTable())
    assert fr.to_string() == "FeatureRecord[featureTag=liga]"
    assert str(fr) == fr.to_string()
