from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import (
    GsubData,
    LangSysTable,
    LookupTable,
    LookupTypeSingleSubstFormat1,
    ScriptTable,
)


def test_default_construction() -> None:
    gd = GsubData()
    assert gd.get_language() == "DEFAULT"
    assert gd.get_active_script_name() == ""
    assert gd.get_script_list() == {}
    assert gd.get_feature_list() == {}
    assert gd.get_glyph_substitution_map() == {}
    assert gd.get_lookup_tables() == ()


def test_round_trip_script_and_lookup_lists() -> None:
    lang_sys = LangSysTable(feature_indices=(0,))
    script = ScriptTable(default_lang_sys_table=lang_sys)
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=1, coverage_table=(10,))
    lookup = LookupTable(lookup_type=1, sub_tables=(sub,))

    gd = GsubData(
        language="ENG",
        active_script_name="latn",
        script_list={"latn": script},
        lookup_tables=(lookup,),
    )
    assert gd.get_language() == "ENG"
    assert gd.get_active_script_name() == "latn"
    assert gd.get_script_list()["latn"] is script
    assert gd.get_lookup_tables() == (lookup,)


def test_is_feature_supported_and_get_feature_table() -> None:
    feat: dict[tuple[int, ...], tuple[int, ...]] = {(70, 70): (500,)}
    gd = GsubData(feature_list={"liga": feat})
    assert gd.is_feature_supported("liga") is True
    assert gd.is_feature_supported("sups") is False
    assert gd.get_feature_table("liga") is feat
    assert gd.get_feature_table("sups") is None


def test_apply_substitution_lookup_list_basic() -> None:
    # ff -> 500, ffi -> 600 (longest-match)
    gd = GsubData(
        glyph_substitution_map={
            (70, 70): (500,),
            (70, 70, 71): (600,),
        }
    )
    assert gd.apply_substitution_lookup_list([70, 70, 71]) == [600]
    assert gd.apply_substitution_lookup_list([70, 70]) == [500]
    assert gd.apply_substitution_lookup_list([70, 99]) == [70, 99]


def test_apply_substitution_lookup_list_empty_inputs() -> None:
    gd = GsubData()
    # Empty input.
    assert gd.apply_substitution_lookup_list([]) == []
    # Empty map — pass through.
    gd2 = GsubData()
    assert gd2.apply_substitution_lookup_list([1, 2, 3]) == [1, 2, 3]


def test_apply_substitution_lookup_list_does_not_mutate_input() -> None:
    gd = GsubData(glyph_substitution_map={(1,): (2,)})
    src = [1, 1, 1]
    out = gd.apply_substitution_lookup_list(src)
    assert src == [1, 1, 1]
    assert out == [2, 2, 2]


def test_apply_substitution_lookup_list_expands_to_multiple_glyphs() -> None:
    # Input glyph 1 expands to two glyphs (10, 11).
    gd = GsubData(glyph_substitution_map={(1,): (10, 11)})
    assert gd.apply_substitution_lookup_list([1, 2]) == [10, 11, 2]


def test_get_feature_returns_per_feature_substitution_map() -> None:
    feature_map: dict[tuple[int, ...], tuple[int, ...]] = {(1,): (2,)}
    gd = GsubData(feature_list={"liga": feature_map})
    assert gd.get_feature("liga") is feature_map
    assert gd.get_feature("missing") is None


def test_get_supported_features_returns_fresh_set() -> None:
    gd = GsubData(feature_list={"liga": {}, "kern": {}})
    supported = gd.get_supported_features()
    assert supported == {"liga", "kern"}
    supported.add("scratch")
    assert "scratch" not in gd.get_supported_features()


def test_no_data_found_sentinel_raises_on_every_accessor() -> None:
    import pytest

    sentinel = GsubData.NO_DATA_FOUND
    with pytest.raises(TypeError):
        sentinel.get_language()
    with pytest.raises(TypeError):
        sentinel.get_active_script_name()
    with pytest.raises(TypeError):
        sentinel.get_script_list()
    with pytest.raises(TypeError):
        sentinel.get_feature_list()
    with pytest.raises(TypeError):
        sentinel.get_glyph_substitution_map()
    with pytest.raises(TypeError):
        sentinel.get_lookup_tables()
    with pytest.raises(TypeError):
        sentinel.is_feature_supported("liga")
    with pytest.raises(TypeError):
        sentinel.get_feature_table("liga")
    with pytest.raises(TypeError):
        sentinel.get_feature("liga")
    with pytest.raises(TypeError):
        sentinel.get_supported_features()
    with pytest.raises(TypeError):
        sentinel.apply_substitution_lookup_list([1, 2, 3])
