from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable


class FakeTTFont:
    def __init__(self, table: Any, glyph_order: list[str]) -> None:
        self._table = table
        self._glyph_order = glyph_order

    def __getitem__(self, key: str) -> Any:
        assert key == "GSUB"
        return SimpleNamespace(table=self._table)

    def getGlyphOrder(self) -> list[str]:
        return self._glyph_order


def _script_record(tag: str, feature_indices: list[int]) -> Any:
    lang_sys = SimpleNamespace(ReqFeatureIndex=0xFFFF, FeatureIndex=feature_indices)
    return SimpleNamespace(
        ScriptTag=tag,
        Script=SimpleNamespace(DefaultLangSys=lang_sys, LangSysRecord=[]),
    )


def _feature_record(tag: str, lookup_indices: list[int]) -> Any:
    return SimpleNamespace(
        FeatureTag=tag,
        Feature=SimpleNamespace(LookupListIndex=lookup_indices),
    )


def _lookup(lookup_type: int, mapping: dict[str, str]) -> Any:
    return SimpleNamespace(
        LookupType=lookup_type,
        SubTable=[SimpleNamespace(mapping=mapping)],
    )


def _table(
    scripts: list[Any],
    features: list[Any],
    lookups: list[Any],
) -> Any:
    return SimpleNamespace(
        ScriptList=SimpleNamespace(ScriptRecord=scripts),
        FeatureList=SimpleNamespace(FeatureRecord=features),
        LookupList=SimpleNamespace(Lookup=lookups),
    )


def test_wave520_populate_deduplicates_scripts_and_features_in_first_seen_order() -> None:
    table = _table(
        [_script_record("latn", []), _script_record("latn", []), _script_record("DFLT", [])],
        [_feature_record(" liga ", []), _feature_record("liga", []), _feature_record("sups", [])],
        [],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(table, [".notdef"]))

    assert gsub.get_supported_script_tags() == {"latn", "DFLT"}
    assert gsub.get_supported_feature_tags() == ["liga", "sups"]

    features = gsub.get_supported_feature_tags()
    features.append("mutated")
    assert gsub.get_supported_feature_tags() == ["liga", "sups"]


def test_wave520_dflt_candidate_falls_back_to_first_supported_script() -> None:
    table = _table(
        [_script_record("latn", [0])],
        [_feature_record("sups", [0])],
        [_lookup(1, {"a": "a.sups"})],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(table, ["a", "a.sups"]))

    assert gsub.get_substitution(0, ["DFLT"], ["sups"]) == 1


def test_wave520_vrt2_suppresses_vert_when_both_features_are_enabled() -> None:
    table = _table(
        [_script_record("latn", [0, 1])],
        [_feature_record("vert", [0]), _feature_record("vrt2", [1])],
        [_lookup(1, {"a": "a.vert"}), _lookup(1, {"a": "a.vrt2"})],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(table, ["a", "a.vert", "a.vrt2"]))

    assert gsub.get_substitution(0, ["latn"], ["vert", "vrt2"]) == 2


def test_wave520_non_single_lookup_type_is_skipped() -> None:
    table = _table(
        [_script_record("latn", [0])],
        [_feature_record("liga", [0])],
        [_lookup(4, {"f": "f_i"})],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(table, ["f", "f_i"]))

    assert gsub.get_substitution(0, ["latn"], ["liga"]) == 0
    assert gsub.get_unsubstitution(0) == 0


def test_wave520_invalid_lookup_indices_are_ignored() -> None:
    table = _table(
        [_script_record("latn", [0])],
        [_feature_record("sups", [42, 0])],
        [_lookup(1, {"a": "a.sups"})],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(table, ["a", "a.sups"]))

    assert gsub.get_substitution(0, ["latn"], ["sups"]) == 1
