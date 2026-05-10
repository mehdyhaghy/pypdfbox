"""Upstream-shaped tests for LookupSubTable variants.

Translated from synthetic equivalents of the assertions exercised by
the GsubWorker test suite (`GsubWorkerForLatinTest`,
`GsubWorkerForBengaliTest`, etc.) plus the `GlyphSubstitutionTableTest`
constructor / accessor checks (no standalone upstream JUnit per
subtable exists — the subtable behavior is exercised through the
worker / parsing tests). We capture the same invariants here at
subtable granularity so a regression in delta arithmetic, indexed
substitution, or ligature shaping fails fast.

Upstream Java references (under
``fontbox/src/main/java/org/apache/fontbox/ttf/table/gsub/``):
- ``LookupTypeSingleSubstFormat1.java``
- ``LookupTypeSingleSubstFormat2.java``
- ``LookupTypeMultipleSubstitutionFormat1.java``
- ``LookupTypeAlternateSubstitutionFormat1.java``
- ``LookupTypeLigatureSubstitutionSubstFormat1.java``
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub import (
    AlternateSetTable,
    CoverageTable,
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


def test_ligature_table_component_glyph_i_ds_mirrors_java_accessor() -> None:
    # Upstream Java method is ``getComponentGlyphIDs()``; snake-case
    # translation drops ``IDs`` into ``i_ds``.
    lt = LigatureTable(
        ligature_glyph=600, component_glyph_ids=(70, 71), component_count=3
    )
    assert lt.get_component_glyph_i_ds() == (70, 71)


def test_ligature_table_to_string_mirrors_java_format() -> None:
    # Java: String.format("%s[ligatureGlyph=%d, componentCount=%d]",
    #     LigatureTable.class.getSimpleName(), ligatureGlyph, componentCount);
    lt = LigatureTable(
        ligature_glyph=600, component_glyph_ids=(70, 71), component_count=3
    )
    assert str(lt) == "LigatureTable[ligatureGlyph=600, componentCount=3]"


# --- CoverageTable ---------------------------------------------------


def test_coverage_table_get_glyph_id_returns_glyph_at_index() -> None:
    # Upstream Java method is ``CoverageTable.getGlyphId(int)``;
    # returns the GID at the requested coverage index.
    cov = CoverageTable(glyph_array=(7, 11, 13))
    assert cov.get_glyph_id(0) == 7
    assert cov.get_glyph_id(1) == 11
    assert cov.get_glyph_id(2) == 13


def test_coverage_table_get_glyph_id_inverse_of_get_coverage_index() -> None:
    # The two accessors are inverses for any in-range GID.
    cov = CoverageTable(glyph_array=(7, 11, 13))
    for gid in cov.get_glyph_array():
        idx = cov.get_coverage_index(gid)
        assert cov.get_glyph_id(idx) == gid


# --- to_string() parity ---------------------------------------------


def test_single_format1_to_string_mirrors_java_format() -> None:
    # Java: String.format(
    #   "LookupTypeSingleSubstFormat1[substFormat=%d,deltaGlyphID=%d]",
    #   getSubstFormat(), deltaGlyphID);
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=7, coverage_table=(1,))
    assert (
        sub.to_string()
        == "LookupTypeSingleSubstFormat1[substFormat=1,deltaGlyphID=7]"
    )


def test_single_format2_to_string_mirrors_java_format() -> None:
    # Java: String.format(
    #   "LookupTypeSingleSubstFormat2[substFormat=%d,substituteGlyphIDs=%s]",
    #   getSubstFormat(), Arrays.toString(substituteGlyphIDs));
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(1, 2, 3), substitute_glyph_ids=(100, 200, 300)
    )
    assert sub.to_string() == (
        "LookupTypeSingleSubstFormat2[substFormat=2,"
        "substituteGlyphIDs=[100, 200, 300]]"
    )


def test_single_format2_get_substitute_glyph_i_ds_mirrors_java_accessor() -> None:
    # Upstream Java method is ``getSubstituteGlyphIDs()``; snake-case
    # translation drops ``IDs`` into ``i_ds``.
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(1, 2), substitute_glyph_ids=(100, 200)
    )
    assert sub.get_substitute_glyph_i_ds() == (100, 200)


def test_sequence_table_to_string_mirrors_java_format() -> None:
    # Java: "SequenceTable{glyphCount=" + glyphCount
    #     + ", substituteGlyphIDs=" + Arrays.toString(substituteGlyphIDs) + '}'
    st = SequenceTable(glyph_count=3, substitute_glyph_ids=(60, 61, 62))
    assert (
        st.to_string()
        == "SequenceTable{glyphCount=3, substituteGlyphIDs=[60, 61, 62]}"
    )


def test_alternate_set_table_to_string_mirrors_java_format() -> None:
    # Java: "AlternateSetTable{glyphCount=" + glyphCount
    #     + ", alternateGlyphIDs=" + Arrays.toString(alternateGlyphIDs) + '}'
    ast = AlternateSetTable(glyph_count=2, alternate_glyph_ids=(900, 901))
    assert (
        ast.to_string()
        == "AlternateSetTable{glyphCount=2, alternateGlyphIDs=[900, 901]}"
    )


def test_ligature_set_table_to_string_mirrors_java_format() -> None:
    # Java: String.format("%s[ligatureCount=%d]",
    #     LigatureSetTable.class.getSimpleName(), ligatureCount);
    lst = LigatureSetTable(
        ligature_tables=(
            LigatureTable(ligature_glyph=1, component_glyph_ids=(2,)),
        )
    )
    assert lst.to_string() == "LigatureSetTable[ligatureCount=1]"


def test_lookup_type_ligature_subst_format1_to_string_mirrors_java_format() -> None:
    # Java: String.format("%s[substFormat=%d]",
    #     LookupTypeLigatureSubstitutionSubstFormat1.class.getSimpleName(),
    #     getSubstFormat());
    sub = LookupTypeLigatureSubstitutionSubstFormat1()
    assert (
        sub.to_string()
        == "LookupTypeLigatureSubstitutionSubstFormat1[substFormat=1]"
    )
