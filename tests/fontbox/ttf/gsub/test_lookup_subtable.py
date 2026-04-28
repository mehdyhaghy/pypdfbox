from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub import (
    AlternateSetTable,
    CoverageTable,
    LigatureSetTable,
    LigatureTable,
    LookupSubTable,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeMultipleSubstitutionFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
    SequenceTable,
)


def test_lookup_subtable_is_abstract() -> None:
    with pytest.raises(TypeError):
        LookupSubTable()  # type: ignore[abstract]


def test_single_format1_passthrough_for_uncovered_glyph() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=5, coverage_table=(10, 11))
    # ``coverage_index < 0`` means the glyph isn't covered — return as-is.
    assert sub.do_substitution(99, -1) == 99


def test_single_format1_applies_delta() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=5, coverage_table=(10, 11))
    assert sub.do_substitution(10, 0) == 15
    assert sub.do_substitution(11, 1) == 16
    assert sub.get_delta_glyph_id() == 5
    assert sub.get_coverage_table() == (10, 11)
    assert sub.get_substitute_format() == 1


def test_single_format1_delta_wraps_modulo_65536() -> None:
    # Delta is signed 16-bit; result is mod 65536 per spec.
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=-1, coverage_table=(0,))
    assert sub.do_substitution(0, 0) == 0xFFFF


def test_single_format2_substitutes_by_index() -> None:
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(20, 21, 22),
        substitute_glyph_ids=(200, 210, 220),
    )
    assert sub.do_substitution(20, 0) == 200
    assert sub.do_substitution(21, 1) == 210
    assert sub.do_substitution(22, 2) == 220
    assert sub.get_substitute_format() == 2
    assert sub.get_substitute_glyph_ids() == (200, 210, 220)
    assert sub.get_coverage_table() == (20, 21, 22)


def test_single_format2_passthrough_for_uncovered() -> None:
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(20,), substitute_glyph_ids=(200,)
    )
    assert sub.do_substitution(99, -1) == 99


def test_single_format2_out_of_bounds_returns_input() -> None:
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(20,), substitute_glyph_ids=(200,)
    )
    # Defensive: malformed font with mismatched arrays must not crash.
    assert sub.do_substitution(20, 5) == 20


def test_ligature_format1_single_glyph_signature_is_unsupported() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1()
    # Mirrors upstream UnsupportedOperationException — ligature shaping
    # cannot be expressed in the single-GID-in / single-GID-out signature.
    with pytest.raises(NotImplementedError):
        sub.do_substitution(1, 0)


def test_ligature_format1_collapses_run_to_ligature_gid() -> None:
    # Coverage on first glyph (f=70). Ligature ff -> 500, ffi -> 600.
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    # Longest match wins, so put longest first per spec
                    # priority — but the implementation should pick the
                    # longest regardless of order.
                    LigatureTable(
                        ligature_glyph=600, component_glyph_ids=(70, 71)
                    ),
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(70,)),
                ),
            ),
        ),
    )
    # f f i -> ffi (longest match).
    assert sub.do_substitution_glyphs([70, 70, 71]) == [600]
    # f f -> ff (shorter match).
    assert sub.do_substitution_glyphs([70, 70]) == [500]
    # f x -> f x (no match).
    assert sub.do_substitution_glyphs([70, 99]) == [70, 99]


def test_ligature_format1_passes_through_uncovered() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(70,)),
                ),
            ),
        ),
    )
    assert sub.do_substitution_glyphs([1, 2, 3]) == [1, 2, 3]


def test_ligature_format1_empty_input() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1()
    assert sub.do_substitution_glyphs([]) == []


def test_ligature_table_getters() -> None:
    lt = LigatureTable(ligature_glyph=42, component_glyph_ids=(1, 2))
    assert lt.get_ligature_glyph() == 42
    assert lt.get_component_glyph_ids() == (1, 2)


def test_ligature_set_table_getter() -> None:
    lt = LigatureTable(ligature_glyph=42, component_glyph_ids=(1,))
    lst = LigatureSetTable(ligature_tables=(lt,))
    assert lst.get_ligature_tables() == (lt,)


def test_ligature_table_component_count_default() -> None:
    # Upstream stores component_count = trailing-components + 1 implicit head.
    lt = LigatureTable(ligature_glyph=42, component_glyph_ids=(1, 2, 3))
    assert lt.get_component_count() == 4


def test_ligature_set_count_default() -> None:
    lt = LigatureTable(ligature_glyph=1, component_glyph_ids=(2,))
    lst = LigatureSetTable(ligature_tables=(lt, lt, lt))
    assert lst.get_ligature_count() == 3


# --- Type 2: Multiple Substitution -----------------------------------


def test_multiple_format1_single_signature_unsupported() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1()
    with pytest.raises(NotImplementedError):
        sub.do_substitution(1, 0)


def test_multiple_format1_expands_to_sequence() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(50,),
        sequence_tables=(
            SequenceTable(glyph_count=3, substitute_glyph_ids=(60, 61, 62)),
        ),
    )
    assert sub.do_substitution_multiple(50, 0) == [60, 61, 62]


def test_multiple_format1_uncovered_passthrough() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1()
    assert sub.do_substitution_multiple(99, -1) == [99]


def test_multiple_format1_out_of_bounds_passthrough() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(50,),
        sequence_tables=(
            SequenceTable(glyph_count=1, substitute_glyph_ids=(60,)),
        ),
    )
    assert sub.do_substitution_multiple(50, 5) == [50]


def test_sequence_table_getters() -> None:
    st = SequenceTable(glyph_count=2, substitute_glyph_ids=(10, 20))
    assert st.get_glyph_count() == 2
    assert st.get_substitute_glyph_ids() == (10, 20)


# --- Type 3: Alternate Substitution ----------------------------------


def test_alternate_format1_single_signature_unsupported() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1()
    with pytest.raises(NotImplementedError):
        sub.do_substitution(1, 0)


def test_alternate_format1_returns_alternate_set() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(80,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=3, alternate_glyph_ids=(800, 801, 802)),
        ),
    )
    assert sub.get_alternate_glyph_ids_for(80, 0) == (800, 801, 802)


def test_alternate_format1_uncovered_returns_empty() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1()
    assert sub.get_alternate_glyph_ids_for(99, -1) == ()


def test_alternate_format1_out_of_bounds_returns_empty() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(80,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=1, alternate_glyph_ids=(800,)),
        ),
    )
    assert sub.get_alternate_glyph_ids_for(80, 7) == ()


def test_alternate_set_table_getters() -> None:
    ast = AlternateSetTable(glyph_count=2, alternate_glyph_ids=(11, 22))
    assert ast.get_glyph_count() == 2
    assert ast.get_alternate_glyph_ids() == (11, 22)


# --- CoverageTable ---------------------------------------------------


def test_coverage_table_index_lookup() -> None:
    cov = CoverageTable(glyph_array=(10, 20, 30))
    assert cov.get_coverage_index(20) == 1
    assert cov.get_coverage_index(99) == -1
    assert cov.get_size() == 3
    assert cov.get_glyph_array() == (10, 20, 30)
    assert cov.get_coverage_format() == 1


def test_lookup_subtable_subst_format_alias() -> None:
    # Upstream Java accessor is ``getSubstFormat`` — kept as alias.
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=1, coverage_table=(1,))
    assert sub.get_subst_format() == sub.get_substitute_format() == 1
