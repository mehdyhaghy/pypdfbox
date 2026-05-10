from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import FeatureTable


def test_default_construction() -> None:
    ft = FeatureTable()
    assert ft.get_feature_params() == 0
    assert ft.get_lookup_list_indices() == ()


def test_explicit_indices_round_trip() -> None:
    ft = FeatureTable(feature_params=0, lookup_list_indices=(0, 2, 5))
    assert ft.get_feature_params() == 0
    assert ft.get_lookup_list_indices() == (0, 2, 5)


def test_lookup_list_indices_is_tuple() -> None:
    ft = FeatureTable(lookup_list_indices=(1,))
    # Tuple semantics — immutable and supports indexing.
    assert isinstance(ft.get_lookup_list_indices(), tuple)
    assert ft.get_lookup_list_indices()[0] == 1


def test_get_lookup_index_count_matches_list_length() -> None:
    # Empty.
    assert FeatureTable().get_lookup_index_count() == 0
    # Three entries.
    ft = FeatureTable(lookup_list_indices=(0, 2, 5))
    assert ft.get_lookup_index_count() == 3


def test_to_string_format_matches_upstream() -> None:
    # Mirrors `FeatureTable[lookupListIndicesCount=<N>]` from upstream.
    assert str(FeatureTable()) == "FeatureTable[lookupListIndicesCount=0]"
    ft = FeatureTable(lookup_list_indices=(1, 2, 3, 4))
    assert str(ft) == "FeatureTable[lookupListIndicesCount=4]"


def test_to_string_method_matches_dunder() -> None:
    # Explicit ``to_string`` mirrors upstream Java naming and must be
    # equal to ``__str__`` (which delegates to it).
    ft = FeatureTable(lookup_list_indices=(1, 2, 3, 4))
    assert ft.to_string() == "FeatureTable[lookupListIndicesCount=4]"
    assert ft.to_string() == str(ft)
