"""Wave 1379 hand-written tests for GSUB lookup Type 2 (multiple substitution).

Type 2 expands one covered glyph into a sequence of replacement glyph
IDs (e.g. decomposing a single precomposed glyph into a base + combining
mark, or a stacked vertical compound into its components). The lookup
exposes :meth:`LookupTypeMultipleSubstitutionFormat1.do_substitution_multiple`
because the single-GID-in / single-GID-out base signature can't express
a one-to-many result.

These tests target integration angles not covered by the earlier wave
files (``test_lookup_subtable.py`` and ``test_gsub_lookup_tail_wave786``):

* Multi-coverage subtables with one Sequence per Coverage position.
* End-to-end run through ``do_substitution_multiple`` across every
  Coverage index, plus the spec-allowed zero-length output corner case
  (rare but legal — Type 2 with ``glyph_count = 0`` deletes the glyph).
* Defensive behaviour when ``sequence_tables`` is shorter than the
  Coverage array (mirrors malformed-font tolerance documented in the
  doctring on the subtable).
* Extractor short-circuit: the data extractor logs and skips when
  Coverage size mismatches Sequence count, matching upstream 3.0.
"""

from __future__ import annotations

import logging

from pypdfbox.fontbox.ttf.gsub import (
    LookupTypeMultipleSubstitutionFormat1,
    SequenceTable,
)
from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)


def test_multiple_substitution_across_multiple_coverage_entries() -> None:
    """One Sequence per covered glyph; verify each maps to its own
    expansion."""
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10, 11, 12),
        sequence_tables=(
            SequenceTable(glyph_count=2, substitute_glyph_ids=(100, 101)),
            SequenceTable(glyph_count=3, substitute_glyph_ids=(110, 111, 112)),
            SequenceTable(glyph_count=1, substitute_glyph_ids=(120,)),
        ),
    )

    assert sub.do_substitution_multiple(10, 0) == [100, 101]
    assert sub.do_substitution_multiple(11, 1) == [110, 111, 112]
    assert sub.do_substitution_multiple(12, 2) == [120]


def test_multiple_substitution_zero_length_sequence_is_glyph_deletion() -> None:
    """``glyph_count = 0`` is spec-legal — the input glyph is dropped."""
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(50,),
        sequence_tables=(SequenceTable(glyph_count=0, substitute_glyph_ids=()),),
    )
    # An empty expansion means "delete this glyph from the run". The
    # subtable surface returns the empty list; the caller is responsible
    # for splicing it into the run.
    assert sub.do_substitution_multiple(50, 0) == []


def test_multiple_substitution_partial_sequence_tables_falls_back() -> None:
    """Malformed font: Coverage promises three entries but only one Sequence
    is present. The subtable must not crash on the missing entries."""
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10, 11, 12),
        sequence_tables=(SequenceTable(glyph_count=1, substitute_glyph_ids=(100,)),),
    )
    assert sub.do_substitution_multiple(10, 0) == [100]
    # Index 1 and 2 are inside Coverage but past the Sequence array —
    # passthrough is the spec-permissive recovery.
    assert sub.do_substitution_multiple(11, 1) == [11]
    assert sub.do_substitution_multiple(12, 2) == [12]


def test_multiple_substitution_extractor_warns_and_skips_on_size_mismatch(
    caplog,
) -> None:
    """The data extractor logs at WARNING level and returns without
    mutating the substitution map when Coverage and Sequence counts
    disagree (upstream behaviour at PDFBox 3.0; the 4.0 fix lives behind
    PDFBOX-5648 which we track but do not port here)."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10, 11),
        sequence_tables=(SequenceTable(glyph_count=1, substitute_glyph_ids=(100,)),),
    )
    glyph_map: dict[tuple[int, ...], int] = {}

    with caplog.at_level(logging.WARNING):
        extractor.extract_data_from_multiple_substitution_format1_table(
            glyph_map, sub
        )

    assert glyph_map == {}
    assert any(
        "coverage table size" in record.message.lower()
        for record in caplog.records
    )


def test_multiple_substitution_extractor_size_match_is_currently_noop() -> None:
    """Upstream PDFBox 3.0 keeps the size check but doesn't store Type-2
    decompositions in the substitution map (the map value is a single
    GID, not a list). The extractor exits silently after the size check
    passes. Pin this so a future port of PDFBOX-5648 forces an explicit
    decision."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10,),
        sequence_tables=(SequenceTable(glyph_count=2, substitute_glyph_ids=(20, 30)),),
    )
    glyph_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_multiple_substitution_format1_table(glyph_map, sub)
    assert glyph_map == {}


def test_multiple_substitution_via_coverage_object_lookup() -> None:
    """End-to-end: resolve the Coverage index via the structured
    :class:`CoverageTable` wrapper, then ask the subtable to expand."""
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(70, 80),
        sequence_tables=(
            SequenceTable(glyph_count=2, substitute_glyph_ids=(700, 701)),
            SequenceTable(glyph_count=2, substitute_glyph_ids=(800, 801)),
        ),
    )
    coverage = sub.get_coverage_object()
    idx = coverage.get_coverage_index(80)
    assert idx == 1
    assert sub.do_substitution_multiple(80, idx) == [800, 801]


def test_multiple_substitution_uncovered_returns_identity_singleton() -> None:
    """``coverage_index < 0`` means "this glyph is not in Coverage" — the
    subtable returns a single-element list with the input glyph
    untouched (so a streaming caller can splice it back in without a
    branch)."""
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10,),
        sequence_tables=(
            SequenceTable(glyph_count=2, substitute_glyph_ids=(100, 101)),
        ),
    )
    assert sub.do_substitution_multiple(999, -1) == [999]
