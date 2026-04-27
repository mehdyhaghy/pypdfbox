from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub import (
    LigatureSetTable,
    LigatureTable,
    LookupSubTable,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
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
