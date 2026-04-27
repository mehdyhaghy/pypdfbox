"""Upstream-shaped tests for ``GsubData``.

There is no standalone ``GsubDataTest`` upstream — the data class is
exercised through ``GsubWorkerForLatinTest`` /
``GlyphSubstitutionDataExtractorTest``. These tests capture the same
invariants those workers depend on (feature lookup, longest-match glyph
substitution) at the data-class level.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import GsubData


def test_default_construction_matches_upstream_empty_state() -> None:
    gd = GsubData()
    assert gd.get_language() == "DEFAULT"
    assert gd.get_active_script_name() == ""
    assert gd.get_script_list() == {}
    assert gd.get_feature_list() == {}
    assert gd.get_glyph_substitution_map() == {}
    assert gd.get_lookup_tables() == ()


def test_is_feature_supported_true_when_present() -> None:
    gd = GsubData(feature_list={"liga": {(1, 2): (3,)}})
    assert gd.is_feature_supported("liga") is True


def test_is_feature_supported_false_when_absent() -> None:
    gd = GsubData(feature_list={"liga": {(1, 2): (3,)}})
    assert gd.is_feature_supported("dlig") is False


def test_get_feature_table_returns_none_when_absent() -> None:
    gd = GsubData()
    assert gd.get_feature_table("liga") is None


def test_apply_substitution_lookup_list_longest_match() -> None:
    gd = GsubData(
        glyph_substitution_map={
            (70, 70): (500,),
            (70, 70, 71): (600,),
        }
    )
    # Longest match wins.
    assert gd.apply_substitution_lookup_list([70, 70, 71]) == [600]
    assert gd.apply_substitution_lookup_list([70, 70]) == [500]
