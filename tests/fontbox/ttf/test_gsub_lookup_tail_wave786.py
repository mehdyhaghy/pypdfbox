from __future__ import annotations

from types import SimpleNamespace

import pytest

from pypdfbox.fontbox.ttf.glyph_positioning_table import GlyphPositioningTable
from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable
from pypdfbox.fontbox.ttf.gsub.lookup_subtable import (
    AlternateSetTable,
    LigatureSetTable,
    LigatureTable,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeMultipleSubstitutionFormat1,
    SequenceTable,
)


def test_gsub_lookup_tail_coverage_getters_and_unsupported_signatures() -> None:
    multiple = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(3,),
        sequence_tables=(SequenceTable(glyph_count=2, substitute_glyph_ids=(4, 5)),),
    )
    alternate = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(6,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(7, 8)),
        ),
    )
    ligature = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(9,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=10, component_glyph_ids=(11,)),
                )
            ),
        ),
    )

    assert multiple.get_coverage_table() == (3,)
    assert multiple.get_coverage_object().get_glyph_array() == (3,)
    assert alternate.get_coverage_table() == (6,)
    assert alternate.get_coverage_object().get_glyph_array() == (6,)
    assert ligature.get_coverage_table() == (9,)
    assert ligature.get_coverage_object().get_glyph_array() == (9,)

    # Multi-glyph lookups don't fit the single-GID-in / single-GID-out
    # signature — upstream throws UnsupportedOperationException; Python's
    # nearest equivalent is ``TypeError``.
    with pytest.raises(TypeError):
        multiple.do_substitution(3, 0)
    with pytest.raises(TypeError):
        alternate.do_substitution(6, 0)
    with pytest.raises(TypeError):
        ligature.do_substitution(9, 0)


def test_ligature_substitution_later_same_length_candidate_wins() -> None:
    subtable = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(20,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=100, component_glyph_ids=(21,)),
                    LigatureTable(ligature_glyph=200, component_glyph_ids=(21,)),
                )
            ),
        ),
    )

    assert subtable.do_substitution_glyphs([20, 21, 22]) == [200, 22]


def test_gsub_substitution_skips_invalid_lookup_indices_and_non_single_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = GlyphSubstitutionTable()
    table._gsub_table = SimpleNamespace(  # noqa: SLF001
        FeatureList=SimpleNamespace(
            FeatureRecord=[
                SimpleNamespace(
                    Feature=SimpleNamespace(LookupListIndex=[99, -1, 0, 1]),
                )
            ]
        ),
        LookupList=SimpleNamespace(
            Lookup=[
                SimpleNamespace(LookupType=2, SubTable=[]),
                SimpleNamespace(
                    LookupType=1,
                    SubTable=[SimpleNamespace(mapping={"a": "a.alt"})],
                ),
            ]
        ),
    )
    table._glyph_order = ["a", "a.alt"]  # noqa: SLF001
    table._glyph_name_to_gid = {"a": 0, "a.alt": 1}  # noqa: SLF001
    monkeypatch.setattr(table, "_select_script_tag", lambda _tags: "latn")
    monkeypatch.setattr(table, "_collect_feature_indices", lambda *_args: [0])

    assert table.get_substitution(0, ["latn"], ["salt"]) == 1
    assert table.get_unsubstitution(1) == 0


def test_gpos_pair_format2_materializes_class_zero_and_named_classes() -> None:
    table = GlyphPositioningTable()
    table._glyph_order = ["A", "V", "X"]  # noqa: SLF001
    table._glyph_name_to_gid = {"A": 0, "V": 1, "X": 2}  # noqa: SLF001
    pairs: dict[tuple[int, int], int] = {}

    table._absorb_pair_format2(  # noqa: SLF001
        SimpleNamespace(
            Coverage=SimpleNamespace(glyphs=["A"]),
            ClassDef1=SimpleNamespace(classDefs={}),
            ClassDef2=SimpleNamespace(classDefs={"V": 1}),
            Class1Record=[
                SimpleNamespace(
                    Class2Record=[
                        SimpleNamespace(Value1=SimpleNamespace(XAdvance=-15)),
                        SimpleNamespace(Value1=SimpleNamespace(XAdvance=-80)),
                    ]
                )
            ],
        ),
        pairs,
    )

    assert pairs == {
        (0, 0): -15,
        (0, 2): -15,
        (0, 1): -80,
    }
