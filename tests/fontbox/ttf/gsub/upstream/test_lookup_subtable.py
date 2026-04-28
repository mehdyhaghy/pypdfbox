"""Upstream-shaped tests for LookupSubTable variants.

Translated from synthetic equivalents of the assertions exercised by
the GsubWorker test suite (`GsubWorkerForLatinTest`,
`GsubWorkerForBengaliTest`, etc.) plus the `GlyphSubstitutionTableTest`
constructor / accessor checks (no standalone upstream JUnit per
subtable exists — the subtable behavior is exercised through the
worker / parsing tests). We capture the same invariants here at
subtable granularity so a regression in delta arithmetic, indexed
substitution, or ligature shaping fails fast.

Upstream Java references:
- fontbox/src/main/java/org/apache/fontbox/ttf/table/gsub/LookupTypeSingleSubstFormat1.java
- fontbox/src/main/java/org/apache/fontbox/ttf/table/gsub/LookupTypeSingleSubstFormat2.java
- fontbox/src/main/java/org/apache/fontbox/ttf/table/gsub/LookupTypeMultipleSubstitutionFormat1.java
- fontbox/src/main/java/org/apache/fontbox/ttf/table/gsub/LookupTypeAlternateSubstitutionFormat1.java
- fontbox/src/main/java/org/apache/fontbox/ttf/table/gsub/LookupTypeLigatureSubstitutionSubstFormat1.java
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub import (
    AlternateSetTable,
    LigatureSetTable,
    LigatureTable,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeMultipleSubstitutionFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
    SequenceTable,
)


# --- Type 1, Format 1 (LookupTypeSingleSubstFormat1) -----------------


def test_single_format1_basic_delta() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=10, coverage_table=(1, 2, 3))
    assert sub.do_substitution(1, 0) == 11
    assert sub.do_substitution(2, 1) == 12
    assert sub.do_substitution(3, 2) == 13


def test_single_format1_negative_delta() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=-1, coverage_table=(5,))
    assert sub.do_substitution(5, 0) == 4


def test_single_format1_uncovered_passthrough() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=10, coverage_table=())
    assert sub.do_substitution(1, -1) == 1


# --- Type 1, Format 2 (LookupTypeSingleSubstFormat2) -----------------


def test_single_format2_indexed_substitute() -> None:
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(1, 2, 3),
        substitute_glyph_ids=(100, 200, 300),
    )
    assert sub.do_substitution(1, 0) == 100
    assert sub.do_substitution(2, 1) == 200
    assert sub.do_substitution(3, 2) == 300


def test_single_format2_uncovered_passthrough() -> None:
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(1,), substitute_glyph_ids=(100,)
    )
    assert sub.do_substitution(99, -1) == 99


# --- Type 2 (LookupTypeMultipleSubstitutionFormat1) ------------------


def test_multiple_format1_single_signature_throws() -> None:
    # Upstream: throws UnsupportedOperationException("not applicable").
    sub = LookupTypeMultipleSubstitutionFormat1()
    with pytest.raises(NotImplementedError):
        sub.do_substitution(1, 0)


def test_multiple_format1_expands_glyph() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(50,),
        sequence_tables=(
            SequenceTable(glyph_count=3, substitute_glyph_ids=(60, 61, 62)),
        ),
    )
    assert sub.do_substitution_multiple(50, 0) == [60, 61, 62]


def test_multiple_format1_sequence_accessors() -> None:
    seq = SequenceTable(glyph_count=2, substitute_glyph_ids=(7, 8))
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(1,), sequence_tables=(seq,)
    )
    assert sub.get_sequence_tables() == (seq,)
    assert sub.get_sequence_tables()[0].get_glyph_count() == 2
    assert sub.get_sequence_tables()[0].get_substitute_glyph_ids() == (7, 8)


# --- Type 3 (LookupTypeAlternateSubstitutionFormat1) -----------------


def test_alternate_format1_single_signature_throws() -> None:
    # Upstream: throws UnsupportedOperationException("not applicable").
    sub = LookupTypeAlternateSubstitutionFormat1()
    with pytest.raises(NotImplementedError):
        sub.do_substitution(1, 0)


def test_alternate_format1_alternate_set_accessors() -> None:
    aset = AlternateSetTable(glyph_count=2, alternate_glyph_ids=(900, 901))
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(80,), alternate_set_tables=(aset,)
    )
    assert sub.get_alternate_set_tables() == (aset,)
    assert sub.get_alternate_set_tables()[0].get_glyph_count() == 2
    assert sub.get_alternate_set_tables()[0].get_alternate_glyph_ids() == (900, 901)


# --- Type 4 (LookupTypeLigatureSubstitutionSubstFormat1) -------------


def test_ligature_format1_single_glyph_signature_unsupported() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1()
    with pytest.raises(NotImplementedError):
        sub.do_substitution(1, 0)


def test_ligature_format1_replaces_run() -> None:
    # Equivalent to the GsubWorkerForLatin "f f i -> ffi" assertion.
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(
                        ligature_glyph=600, component_glyph_ids=(70, 71)
                    ),
                ),
            ),
        ),
    )
    assert sub.do_substitution_glyphs([70, 70, 71]) == [600]


def test_ligature_format1_set_accessors() -> None:
    lt = LigatureTable(ligature_glyph=600, component_glyph_ids=(70, 71))
    lst = LigatureSetTable(ligature_tables=(lt,))
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,), ligature_set_tables=(lst,)
    )
    assert sub.get_ligature_set_tables() == (lst,)
    assert sub.get_ligature_set_tables()[0].get_ligature_count() == 1
