"""Coverage-boost tests for :class:`GlyphSubstitutionDataExtractor`.

Targets the warning-and-skip branches (size mismatches), the unknown-
subtable fallthrough, the ``None`` lang-sys-table guard, the
multiple-substitution dispatcher branch, and the override-debug branch
in :meth:`put_new_substitution_entry`.
"""

from __future__ import annotations

import logging

from pypdfbox.fontbox.ttf.gsub import (
    AlternateSetTable,
    FeatureRecord,
    FeatureTable,
    GlyphSubstitutionDataExtractor,
    LangSysTable,
    LigatureSetTable,
    LigatureTable,
    LookupSubTable,
    LookupTable,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeMultipleSubstitutionFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
    SequenceTable,
)

# ----------------------------------------------------------------------
# populate_gsub_data — None lang-sys-table guard (line 149)
# ----------------------------------------------------------------------


def test_populate_gsub_data_with_none_lang_sys_table_is_noop() -> None:
    """Mirror upstream's early-return when no LangSysTable is supplied.

    Covered: line 149 (`if lang_sys_table is None: return`).
    """
    extractor = GlyphSubstitutionDataExtractor()
    out: dict[str, dict[tuple[int, ...], int]] = {}
    extractor.populate_gsub_data(out, None, [], [])
    assert out == {}


def test_populate_gsub_data_skips_out_of_range_feature_indices() -> None:
    """Feature indices past the FeatureList length are ignored.

    Mirrors upstream's bounds check in ``populateGsubData``.
    """
    extractor = GlyphSubstitutionDataExtractor()
    out: dict[str, dict[tuple[int, ...], int]] = {}
    lang_sys = LangSysTable(feature_indices=(99,))
    extractor.populate_gsub_data(out, lang_sys, [], [])
    assert out == {}


# ----------------------------------------------------------------------
# extract_data — multiple-substitution dispatch + unknown fallback
# (lines 212-215, 216-222)
# ----------------------------------------------------------------------


def test_extract_data_dispatches_multiple_substitution() -> None:
    """The multiple-substitution dispatch branch is exercised.

    Covered: lines 212-215 (elif branch into
    ``extract_data_from_multiple_substitution_format1_table``).
    """
    extractor = GlyphSubstitutionDataExtractor()
    seq = SequenceTable(glyph_count=2, substitute_glyph_ids=(60, 61))
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(70,),
        sequence_tables=(seq,),
    )
    table = LookupTable(lookup_type=2, sub_tables=(sub,))
    out: dict[tuple[int, ...], int] = {}
    extractor.extract_data(out, table)
    # The 3.0 port intentionally leaves the map empty for multi-subst;
    # the dispatch path itself should not raise.
    assert out == {}


class _UnknownSubTable(LookupSubTable):
    """A subtable type none of the extract dispatchers recognise."""

    def __init__(self) -> None:
        super().__init__(substitute_format=99, coverage_table=None)

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        return original_glyph_id


def test_extract_data_logs_and_skips_unknown_subtable_type(
    caplog: object,
) -> None:
    """Unknown subtable types log at debug and don't raise.

    Covered: lines 216-222 (else branch + LOG.debug call).
    """
    extractor = GlyphSubstitutionDataExtractor()
    table = LookupTable(lookup_type=99, sub_tables=(_UnknownSubTable(),))
    out: dict[tuple[int, ...], int] = {}
    with caplog.at_level(  # type: ignore[attr-defined]
        logging.DEBUG, logger="pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor"
    ):
        extractor.extract_data(out, table)
    assert out == {}
    assert any("is not yet supported" in rec.message for rec in caplog.records)  # type: ignore[attr-defined]


# ----------------------------------------------------------------------
# single subst format 2 — coverage / substitute size mismatch
# (lines 250-256)
# ----------------------------------------------------------------------


def test_single_subst_format2_size_mismatch_short_circuits(caplog: object) -> None:
    """Mismatched coverage vs substitute array sizes warn and skip.

    Covered: lines 250-256 (LOG.warning + early return).
    """
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeSingleSubstFormat2(
        substitute_glyph_ids=(100,),
        coverage_table=(20, 21, 22),
    )
    out: dict[tuple[int, ...], int] = {}
    with caplog.at_level(  # type: ignore[attr-defined]
        logging.WARNING,
        logger="pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor",
    ):
        extractor.extract_data_from_single_subst_table_format2_table(out, sub)
    assert out == {}
    assert any(
        "coverage table size" in rec.message for rec in caplog.records  # type: ignore[attr-defined]
    )


# ----------------------------------------------------------------------
# multiple_substitution_format1 — coverage / sequence size mismatch
# (lines 272-281)
# ----------------------------------------------------------------------


def test_multiple_substitution_size_mismatch_short_circuits(caplog: object) -> None:
    """Mismatched coverage vs sequence table sizes warn and skip.

    Covered: lines 272-281 (LOG.warning + early return).
    """
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(70, 71, 72),
        sequence_tables=(SequenceTable(glyph_count=1, substitute_glyph_ids=(80,)),),
    )
    out: dict[tuple[int, ...], int] = {}
    with caplog.at_level(  # type: ignore[attr-defined]
        logging.WARNING,
        logger="pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor",
    ):
        extractor.extract_data_from_multiple_substitution_format1_table(out, sub)
    assert out == {}
    assert any(
        "coverage table size" in rec.message for rec in caplog.records  # type: ignore[attr-defined]
    )


def test_multiple_substitution_balanced_sizes_is_still_noop_in_3x() -> None:
    """3.x extractor records nothing even on a balanced multi-subst table.

    Confirms the documented "implemented in 4.0 since PDFBOX-5648" gap.
    """
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(70,),
        sequence_tables=(SequenceTable(glyph_count=2, substitute_glyph_ids=(80, 81)),),
    )
    out: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_multiple_substitution_format1_table(out, sub)
    assert out == {}


# ----------------------------------------------------------------------
# alternate substitution — coverage / set size mismatch (315-321)
# ----------------------------------------------------------------------


def test_alternate_substitution_size_mismatch_short_circuits(caplog: object) -> None:
    """Mismatched coverage vs alternate-set sizes warn and skip.

    Covered: lines 315-321 (LOG.warning + early return).
    """
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(40, 41),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(50, 51)),
        ),
    )
    out: dict[tuple[int, ...], int] = {}
    with caplog.at_level(  # type: ignore[attr-defined]
        logging.WARNING,
        logger="pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor",
    ):
        extractor.extract_data_from_alternate_substitution_subst_format1_table(out, sub)
    assert out == {}
    assert any(
        "alternate set tables" in rec.message
        or "atlternate set tables" in rec.message  # upstream typo
        for rec in caplog.records  # type: ignore[attr-defined]
    )


def test_alternate_substitution_all_match_coverage_records_nothing() -> None:
    """When every alternate equals the coverage glyph, no substitution wins."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(40,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=1, alternate_glyph_ids=(40,)),
        ),
    )
    out: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_alternate_substitution_subst_format1_table(out, sub)
    assert out == {}


# ----------------------------------------------------------------------
# put_new_substitution_entry — old-value override logs at debug (361)
# ----------------------------------------------------------------------


def test_put_new_substitution_entry_override_logs(caplog: object) -> None:
    """A second put for the same key overwrites and logs at debug.

    Covered: line 361 (LOG.debug "is trying to override the oldValue").
    """
    out: dict[tuple[int, ...], int] = {}
    GlyphSubstitutionDataExtractor.put_new_substitution_entry(out, 42, [1, 2])
    with caplog.at_level(  # type: ignore[attr-defined]
        logging.DEBUG,
        logger="pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor",
    ):
        GlyphSubstitutionDataExtractor.put_new_substitution_entry(out, 99, [1, 2])
    assert out[(1, 2)] == 99
    assert any(
        "is trying to override the oldValue" in rec.message
        for rec in caplog.records  # type: ignore[attr-defined]
    )


# ----------------------------------------------------------------------
# Smoke — multiple substitution dispatched through full pipeline
# ----------------------------------------------------------------------


def test_extract_data_handles_ligature_lookup_through_dispatch() -> None:
    """End-to-end check that ligature subtables still flow through
    :meth:`extract_data` (regression guard on the isinstance order).
    """
    extractor = GlyphSubstitutionDataExtractor()
    lig = LigatureTable(
        ligature_glyph=900,
        component_glyph_ids=(1, 2),
        component_count=3,
    )
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(0,),
        ligature_set_tables=(LigatureSetTable(ligature_tables=(lig,)),),
    )
    table = LookupTable(lookup_type=4, sub_tables=(sub,))
    out: dict[tuple[int, ...], int] = {}
    extractor.extract_data(out, table)
    assert out == {(1, 2): 900}


def test_extract_data_handles_single_format1_through_dispatch() -> None:
    """End-to-end check that single-format1 still flows through
    :meth:`extract_data` (regression guard on the isinstance order)."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=2, coverage_table=(10,))
    table = LookupTable(lookup_type=1, sub_tables=(sub,))
    out: dict[tuple[int, ...], int] = {}
    extractor.extract_data(out, table)
    assert out == {(10,): 12}


def test_extract_data_handles_alternate_through_dispatch() -> None:
    """End-to-end check that alternate subst flows through :meth:`extract_data`."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(40,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(40, 41)),
        ),
    )
    table = LookupTable(lookup_type=3, sub_tables=(sub,))
    out: dict[tuple[int, ...], int] = {}
    extractor.extract_data(out, table)
    assert out == {(40,): 41}


# ----------------------------------------------------------------------
# Feature record with no feature_table — defensive None handling
# ----------------------------------------------------------------------


def test_populate_gsub_data_from_feature_with_none_feature_table() -> None:
    """A FeatureRecord with ``feature_table=None`` records an empty entry."""
    extractor = GlyphSubstitutionDataExtractor()
    out: dict[str, dict[tuple[int, ...], int]] = {}
    rec = FeatureRecord(feature_tag="liga", feature_table=None)
    extractor.populate_gsub_data_from_feature(out, rec, [])
    assert "liga" in out
    assert dict(out["liga"]) == {}


def test_populate_gsub_data_from_feature_skips_out_of_range_lookup() -> None:
    """Lookup indices past the lookup-list length are silently skipped."""
    extractor = GlyphSubstitutionDataExtractor()
    out: dict[str, dict[tuple[int, ...], int]] = {}
    rec = FeatureRecord(
        feature_tag="liga",
        feature_table=FeatureTable(lookup_list_indices=(5,)),
    )
    extractor.populate_gsub_data_from_feature(out, rec, [])
    assert dict(out["liga"]) == {}
