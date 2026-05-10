"""Hand-written tests for :class:`GlyphSubstitutionDataExtractor`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import (
    AlternateSetTable,
    FeatureRecord,
    FeatureTable,
    GlyphSubstitutionDataExtractor,
    LangSysTable,
    LigatureSetTable,
    LigatureTable,
    LookupTable,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
    ScriptTable,
)
from pypdfbox.fontbox.ttf.model import Language, MapBackedGsubData


def _single_format1_lookup() -> LookupTable:
    sub = LookupTypeSingleSubstFormat1(
        delta_glyph_id=5,
        coverage_table=(10, 11, 12),
    )
    return LookupTable(lookup_type=1, sub_tables=(sub,))


def _single_format2_lookup() -> LookupTable:
    sub = LookupTypeSingleSubstFormat2(
        substitute_glyph_ids=(100, 101, 102),
        coverage_table=(20, 21, 22),
    )
    return LookupTable(lookup_type=1, sub_tables=(sub,))


def _ligature_lookup() -> LookupTable:
    lig = LigatureTable(
        ligature_glyph=500,
        component_glyph_ids=(31, 32),
        component_count=3,
    )
    lig_set = LigatureSetTable(ligature_tables=(lig,))
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(30,),
        ligature_set_tables=(lig_set,),
    )
    return LookupTable(lookup_type=4, sub_tables=(sub,))


def _alternate_lookup() -> LookupTable:
    alts = AlternateSetTable(
        glyph_count=2, alternate_glyph_ids=(40, 41)
    )
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(40,),
        alternate_set_tables=(alts,),
    )
    return LookupTable(lookup_type=3, sub_tables=(sub,))


def _make_feature(tag: str, lookup_index: int) -> FeatureRecord:
    return FeatureRecord(
        feature_tag=tag,
        feature_table=FeatureTable(lookup_list_indices=(lookup_index,)),
    )


def test_single_substitution_format1_data() -> None:
    extractor = GlyphSubstitutionDataExtractor()
    script = ScriptTable(
        default_lang_sys_table=LangSysTable(feature_indices=(0,))
    )
    data = extractor.get_gsub_data(
        {"latn": script},
        [_make_feature("liga", 0)],
        [_single_format1_lookup()],
    )
    assert isinstance(data, MapBackedGsubData)
    assert data.get_language() is Language.LATIN
    assert data.get_active_script_name() == "latn"
    feature = data.get_feature("liga")
    assert feature.get_all_glyph_ids_for_substitution() == {(10,), (11,), (12,)}
    assert feature.get_replacement_for_glyphs([10]) == 15
    assert feature.get_replacement_for_glyphs([11]) == 16


def test_single_substitution_format2_data() -> None:
    extractor = GlyphSubstitutionDataExtractor()
    script = ScriptTable(
        default_lang_sys_table=LangSysTable(feature_indices=(0,))
    )
    data = extractor.get_gsub_data(
        {"latn": script},
        [_make_feature("liga", 0)],
        [_single_format2_lookup()],
    )
    feature = data.get_feature("liga")
    assert feature.get_replacement_for_glyphs([20]) == 100
    assert feature.get_replacement_for_glyphs([21]) == 101


def test_ligature_substitution_data() -> None:
    extractor = GlyphSubstitutionDataExtractor()
    script = ScriptTable(
        default_lang_sys_table=LangSysTable(feature_indices=(0,))
    )
    data = extractor.get_gsub_data(
        {"latn": script},
        [_make_feature("liga", 0)],
        [_ligature_lookup()],
    )
    feature = data.get_feature("liga")
    # Trailing components only — upstream's data extractor doesn't
    # include the first coverage glyph in the key.
    assert feature.get_replacement_for_glyphs([31, 32]) == 500


def test_alternate_substitution_first_distinct_wins() -> None:
    extractor = GlyphSubstitutionDataExtractor()
    script = ScriptTable(
        default_lang_sys_table=LangSysTable(feature_indices=(0,))
    )
    data = extractor.get_gsub_data(
        {"latn": script},
        [_make_feature("aalt", 0)],
        [_alternate_lookup()],
    )
    feature = data.get_feature("aalt")
    # The first alternate (40) equals the coverage glyph and is
    # skipped — 41 is the chosen substitute.
    assert feature.get_replacement_for_glyphs([40]) == 41


def test_returns_none_when_no_language_matches() -> None:
    extractor = GlyphSubstitutionDataExtractor()
    # Script tag the Language enum doesn't recognise.
    data = extractor.get_gsub_data(
        {"xxxx": ScriptTable()},
        [],
        [],
    )
    assert data is None


def test_get_gsub_data_for_script_uses_unspecified_language() -> None:
    extractor = GlyphSubstitutionDataExtractor()
    script = ScriptTable(
        default_lang_sys_table=LangSysTable(feature_indices=(0,))
    )
    data = extractor.get_gsub_data_for_script(
        "custom",
        script,
        [_make_feature("liga", 0)],
        [_single_format1_lookup()],
    )
    assert data.get_language() is Language.UNSPECIFIED
    assert data.get_active_script_name() == "custom"
    assert data.is_feature_supported("liga")


def test_lang_sys_tables_in_addition_to_default() -> None:
    extractor = GlyphSubstitutionDataExtractor()
    script = ScriptTable(
        default_lang_sys_table=LangSysTable(feature_indices=(0,)),
        lang_sys_tables={"ENG": LangSysTable(feature_indices=(1,))},
    )
    data = extractor.get_gsub_data(
        {"latn": script},
        [
            _make_feature("liga", 0),
            _make_feature("ccmp", 1),
        ],
        [_single_format1_lookup(), _single_format2_lookup()],
    )
    assert data.get_supported_features() == {"liga", "ccmp"}
