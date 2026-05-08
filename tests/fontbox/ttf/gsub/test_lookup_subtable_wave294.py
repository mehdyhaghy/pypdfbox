from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import (
    LigatureSetTable,
    LigatureTable,
    LookupTypeLigatureSubstitutionSubstFormat1,
)


def test_ligature_format1_ignores_empty_component_candidate() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(10,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=999, component_glyph_ids=()),
                ),
            ),
        ),
    )

    assert sub.do_substitution_glyphs([10, 20]) == [10, 20]


def test_ligature_format1_empty_component_candidate_does_not_mask_valid_match() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(10,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=999, component_glyph_ids=()),
                    LigatureTable(ligature_glyph=1200, component_glyph_ids=(20,)),
                ),
            ),
        ),
    )

    assert sub.do_substitution_glyphs([10, 20, 30]) == [1200, 30]
