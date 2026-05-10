from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import FeatureRecord, FeatureTable


def test_default_construction() -> None:
    fr = FeatureRecord()
    assert fr.get_feature_tag() == ""
    assert fr.get_feature_table() is None


def test_round_trip_tag_and_table() -> None:
    table = FeatureTable(feature_params=0, lookup_list_indices=(3, 7))
    fr = FeatureRecord(feature_tag="liga", feature_table=table)
    assert fr.get_feature_tag() == "liga"
    assert fr.get_feature_table() is table
    # Field access mirrors getter access.
    assert fr.feature_tag == fr.get_feature_tag()
    assert fr.feature_table is fr.get_feature_table()


def test_padded_tag_preserved_verbatim() -> None:
    # Upstream pads short tags with spaces; constructor doesn't trim.
    fr = FeatureRecord(feature_tag="cv1 ", feature_table=FeatureTable())
    assert fr.get_feature_tag() == "cv1 "
    assert fr.get_feature_tag().strip() == "cv1"


def test_to_string_matches_upstream_format() -> None:
    # Mirrors upstream ``FeatureRecord[featureTag=<tag>]``.
    fr = FeatureRecord(feature_tag="liga", feature_table=FeatureTable())
    assert fr.to_string() == "FeatureRecord[featureTag=liga]"
    assert str(fr) == fr.to_string()


def test_to_string_includes_padded_tag_verbatim() -> None:
    fr = FeatureRecord(feature_tag="cv1 ", feature_table=FeatureTable())
    assert fr.to_string() == "FeatureRecord[featureTag=cv1 ]"
