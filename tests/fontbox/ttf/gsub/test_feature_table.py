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
