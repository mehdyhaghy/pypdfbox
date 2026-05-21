"""Wave 1379 hand-written tests for GSUB lookup Type 3 (alternate substitution).

Type 3 exposes a *set* of alternate glyph IDs for a covered glyph
(e.g. stylistic / swash / titling variants). The lookup doesn't pick a
winner — that is the layout engine's job. In pypdfbox's worker dispatch
the AALT worker walks the Coverage and emits the *first* alternate as
the canonical substitution; the underlying subtable still exposes the
full candidate set via
:meth:`LookupTypeAlternateSubstitutionFormat1.get_alternate_glyph_ids_for`.

These tests cover angles not addressed by ``test_lookup_subtable.py``:

* Multi-coverage subtables with one AlternateSet per Coverage position.
* Extractor: how does ``GlyphSubstitutionDataExtractor`` reduce the
  candidate set into the ``glyph_run -> substitute_glyph_id`` map?
  Upstream picks the first alternate that *differs* from the Coverage
  glyph; pin that rule including the "all alternates equal coverage"
  degenerate case (extractor leaves the slot empty).
* Coverage / AlternateSet size mismatch: extractor logs and skips
  without partial population.
"""

from __future__ import annotations

import logging

from pypdfbox.fontbox.ttf.gsub import (
    AlternateSetTable,
    LookupTypeAlternateSubstitutionFormat1,
)
from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)


def test_alternate_multi_coverage_each_returns_own_set() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(10, 11, 12),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(100, 101)),
            AlternateSetTable(glyph_count=1, alternate_glyph_ids=(110,)),
            AlternateSetTable(glyph_count=3, alternate_glyph_ids=(120, 121, 122)),
        ),
    )
    assert sub.get_alternate_glyph_ids_for(10, 0) == (100, 101)
    assert sub.get_alternate_glyph_ids_for(11, 1) == (110,)
    assert sub.get_alternate_glyph_ids_for(12, 2) == (120, 121, 122)


def test_alternate_extractor_picks_first_differing_candidate() -> None:
    """Upstream extractor: the first alternate that *isn't equal to the
    Coverage glyph* wins. Equal alternates are skipped (degenerate fonts
    sometimes emit a Coverage glyph at index 0 of the AlternateSet)."""
    extractor = GlyphSubstitutionDataExtractor()
    # Coverage glyph 30 has alternates [30, 31, 32] — the first differing
    # one is 31, which is what the extractor should record.
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(30,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=3, alternate_glyph_ids=(30, 31, 32)),
        ),
    )
    glyph_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_alternate_substitution_subst_format1_table(
        glyph_map, sub
    )
    assert glyph_map == {(30,): 31}


def test_alternate_extractor_skips_when_all_alternates_equal_coverage() -> None:
    """Degenerate AlternateSet where every candidate equals the Coverage
    glyph — the extractor emits no entry (the entire ``for`` loop falls
    through without a ``break``)."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(40,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(40, 40)),
        ),
    )
    glyph_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_alternate_substitution_subst_format1_table(
        glyph_map, sub
    )
    assert glyph_map == {}


def test_alternate_extractor_skips_on_size_mismatch(caplog) -> None:
    """Malformed font: Coverage and AlternateSet counts disagree.
    Upstream logs at WARNING and exits without partial population."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(50, 51),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=1, alternate_glyph_ids=(500,)),
        ),
    )
    glyph_map: dict[tuple[int, ...], int] = {}
    with caplog.at_level(logging.WARNING):
        extractor.extract_data_from_alternate_substitution_subst_format1_table(
            glyph_map, sub
        )
    assert glyph_map == {}
    assert any(
        "coverage table size" in record.message.lower()
        for record in caplog.records
    )


def test_alternate_extractor_extracts_first_when_coverage_not_first() -> None:
    """The first alternate isn't always equal to Coverage; common case is
    "alternate[0] is the variant the font designer wants to expose first
    via AALT/SALT". Pin that the extractor picks alternate[0] when it's
    already different."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(60,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(600, 601)),
        ),
    )
    glyph_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_alternate_substitution_subst_format1_table(
        glyph_map, sub
    )
    assert glyph_map == {(60,): 600}


def test_alternate_extractor_handles_multiple_coverage_entries() -> None:
    """Multi-coverage Alternate subtable produces one substitution per
    Coverage entry."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(70, 80),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(700, 701)),
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(800, 801)),
        ),
    )
    glyph_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_alternate_substitution_subst_format1_table(
        glyph_map, sub
    )
    assert glyph_map == {(70,): 700, (80,): 800}


def test_alternate_empty_set_yields_empty_candidate_tuple() -> None:
    """An AlternateSet declared with ``glyph_count = 0`` is legal in the
    spec (no candidates). The accessor must return an empty tuple, not
    fail."""
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(90,),
        alternate_set_tables=(AlternateSetTable(glyph_count=0, alternate_glyph_ids=()),),
    )
    assert sub.get_alternate_glyph_ids_for(90, 0) == ()


def test_alternate_via_coverage_object_lookup() -> None:
    """End-to-end: locate the Coverage index via the structured wrapper,
    then ask the subtable for the candidate set."""
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(110, 120, 130),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=1, alternate_glyph_ids=(111,)),
            AlternateSetTable(glyph_count=1, alternate_glyph_ids=(121,)),
            AlternateSetTable(glyph_count=1, alternate_glyph_ids=(131,)),
        ),
    )
    coverage = sub.get_coverage_object()
    assert coverage.get_coverage_index(120) == 1
    assert sub.get_alternate_glyph_ids_for(120, 1) == (121,)
    # Uncovered glyph returns -1 and the accessor's defensive empty tuple.
    assert coverage.get_coverage_index(999) == -1
    assert sub.get_alternate_glyph_ids_for(999, -1) == ()
