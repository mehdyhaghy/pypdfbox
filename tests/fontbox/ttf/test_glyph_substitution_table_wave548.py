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


def _lang_sys(feature_indices: list[int], required: int = 0xFFFF) -> Any:
    return SimpleNamespace(ReqFeatureIndex=required, FeatureIndex=feature_indices)


def _script_record(
    tag: str,
    default_indices: list[int],
    *,
    lang_systems: list[Any] | None = None,
    required: int = 0xFFFF,
) -> Any:
    return SimpleNamespace(
        ScriptTag=tag,
        Script=SimpleNamespace(
            DefaultLangSys=_lang_sys(default_indices, required),
            LangSysRecord=[
                SimpleNamespace(LangSys=lang_sys)
                for lang_sys in (lang_systems or [])
            ],
        ),
    )


def _feature_record(tag: str, lookup_indices: list[int]) -> Any:
    return SimpleNamespace(
        FeatureTag=tag,
        Feature=SimpleNamespace(LookupListIndex=lookup_indices),
    )


def _lookup(mapping: dict[str, str], lookup_type: int = 1) -> Any:
    return SimpleNamespace(
        LookupType=lookup_type,
        SubTable=[SimpleNamespace(mapping=mapping)],
    )


def _table(scripts: list[Any], features: list[Any], lookups: list[Any]) -> Any:
    return SimpleNamespace(
        ScriptList=SimpleNamespace(ScriptRecord=scripts),
        FeatureList=SimpleNamespace(FeatureRecord=features),
        LookupList=SimpleNamespace(Lookup=lookups),
    )


def test_wave548_populate_from_fonttools_handles_missing_gsub_table() -> None:
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(None, [".notdef", "a"]))

    assert gsub.get_initialized() is True
    assert gsub.get_raw_table() is None
    assert gsub.get_supported_script_tags() == set()
    assert gsub.get_supported_feature_tags() == []
    assert gsub.get_substitution(1, ["latn"], ["sups"]) == 1


def test_wave548_required_and_language_system_features_are_collected_once() -> None:
    table = _table(
        [
            _script_record(
                "latn",
                [1, 2],
                lang_systems=[_lang_sys([2, 3], required=0)],
                required=0,
            )
        ],
        [
            _feature_record("zero", [0]),
            _feature_record("one", [1]),
            _feature_record("two", [2]),
            _feature_record("three", [3]),
        ],
        [
            _lookup({"a": "a.zero"}),
            _lookup({"a.zero": "a.one"}),
            _lookup({"a.one": "a.two"}),
            _lookup({"a.two": "a.three"}),
        ],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(
        FakeTTFont(table, ["a", "a.zero", "a.one", "a.two", "a.three"])
    )

    assert gsub.get_substitution(0, ["latn"], None) == 4
    assert gsub.get_unsubstitution(4) == 0


def test_wave548_enabled_feature_order_controls_lookup_order() -> None:
    table = _table(
        [_script_record("latn", [0, 1])],
        [_feature_record("first", [0]), _feature_record("second", [1])],
        [_lookup({"a.second": "a.final"}), _lookup({"a": "a.second"})],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(table, ["a", "a.second", "a.final"]))

    assert gsub.get_substitution(0, ["latn"], ["second", "first"]) == 2


def test_wave548_lookup_indices_for_duplicate_feature_records_are_deduplicated() -> None:
    table = _table(
        [_script_record("latn", [])],
        [
            _feature_record("salt", [2, 1, 2]),
            _feature_record("liga", [4]),
            _feature_record("salt", [1, 3]),
        ],
        [],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(table, [".notdef"]))

    assert gsub.get_lookup_indices_for_feature("salt") == [2, 1, 3]


def test_wave548_single_lookup_ignores_unknown_destination_and_invalid_gid() -> None:
    table = _table(
        [_script_record("latn", [0])],
        [_feature_record("sups", [0])],
        [_lookup({"a": "missing.glyph", "b": "b.sups"})],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(table, ["a", "b", "b.sups"]))

    assert gsub.get_substitution(0, ["latn"], ["sups"]) == 0
    assert gsub.get_substitution(99, ["latn"], ["sups"]) == 99


def test_wave548_dflt_reuses_last_supported_script_when_available() -> None:
    table = _table(
        [
            _script_record("latn", [0]),
            _script_record("cyrl", [1]),
        ],
        [_feature_record("latn", [0]), _feature_record("cyrl", [1])],
        [_lookup({"a": "a.latn"}), _lookup({"a": "a.cyrl"})],
    )
    gsub = GlyphSubstitutionTable()
    gsub.populate_from_fonttools(FakeTTFont(table, ["a", "a.latn", "a.cyrl"]))

    assert gsub._select_script_tag(("cyrl",)) == "cyrl"  # noqa: SLF001
    assert gsub._select_script_tag(("DFLT",)) == "cyrl"  # noqa: SLF001
