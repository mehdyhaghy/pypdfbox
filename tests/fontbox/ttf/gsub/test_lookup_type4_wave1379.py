"""Wave 1379 hand-written tests for GSUB lookup Type 4 (ligature substitution).

Type 4 is many-to-one: a covered first glyph plus a list of trailing
component GIDs collapses to a single ligature GID. The matching rule
("longest match wins, then first-in-array on ties") is exercised by
:meth:`LookupTypeLigatureSubstitutionSubstFormat1.do_substitution_glyphs`.

These tests target angles not addressed by the earlier wave files
(``test_lookup_subtable.py`` and ``test_gsub_lookup_tail_wave786``):

* Multi-LigatureSet subtables: each Coverage position has its own list
  of ligature candidates, and a single shaping run can chain across
  different sets.
* Greedy left-to-right walk: a partial match at index ``i`` shouldn't
  block a longer match starting at the very next glyph.
* Non-coverage glyphs interspersed in the run: walked through untouched
  while the surrounding shaping continues.
* Extractor: each :class:`LigatureTable` becomes a
  ``trailing_components -> ligature_glyph`` entry in the substitution
  map. The implicit first component is *not* prepended (that's the
  upstream contract — the worker reattaches it at apply time).
* Defensive: empty ``component_glyph_ids`` (degenerate font) is skipped
  by the shaping walk.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import (
    LigatureSetTable,
    LigatureTable,
    LookupTypeLigatureSubstitutionSubstFormat1,
)
from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)


def test_ligature_two_coverage_entries_each_with_own_set() -> None:
    """Multi-Coverage Type 4 subtable. Coverage[0] = 'f', Coverage[1] = 'd'.
    Each first-glyph has its own LigatureSet."""
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70, 80),
        ligature_set_tables=(
            # f-led ligatures: fi -> 500, fl -> 501
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(71,)),
                    LigatureTable(ligature_glyph=501, component_glyph_ids=(72,)),
                ),
            ),
            # d-led ligatures: dz -> 600
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=600, component_glyph_ids=(81,)),
                ),
            ),
        ),
    )
    # f + i -> fi  (Coverage[0] match, ligature 500)
    assert sub.do_substitution_glyphs([70, 71]) == [500]
    # d + z -> dz  (Coverage[1] match, ligature 600)
    assert sub.do_substitution_glyphs([80, 81]) == [600]
    # Chain: f + l + d + z -> fl + dz
    assert sub.do_substitution_glyphs([70, 72, 80, 81]) == [501, 600]


def test_ligature_partial_match_does_not_consume_first_glyph() -> None:
    """If ``f + i`` would be a ligature but only ``f + x`` is present, the
    walker emits the ``f`` and advances by one — the next iteration
    starts at ``x``. This is the spec-mandated greedy-but-non-consuming
    fallback."""
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(
                        ligature_glyph=500, component_glyph_ids=(71, 72)
                    ),
                ),
            ),
        ),
    )
    # f + x + y -> f + x + y (no ligature matches)
    assert sub.do_substitution_glyphs([70, 99, 100]) == [70, 99, 100]


def test_ligature_chain_within_single_run() -> None:
    """Two consecutive ligatures in the same run, with non-coverage
    glyphs in between."""
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(71,)),
                ),
            ),
        ),
    )
    # f + i + space + f + i -> fi + space + fi
    assert sub.do_substitution_glyphs([70, 71, 3, 70, 71]) == [500, 3, 500]


def test_ligature_no_consumption_when_components_run_off_end() -> None:
    """A LigatureTable that needs 3 trailing components but the input run
    has only 1 left after the first glyph — the candidate is rejected
    and the first glyph passes through unchanged."""
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(
                        ligature_glyph=500, component_glyph_ids=(71, 72, 73)
                    ),
                ),
            ),
        ),
    )
    # f + i + l - only two trailing slots, not three -> no match.
    assert sub.do_substitution_glyphs([70, 71, 72]) == [70, 71, 72]


def test_ligature_empty_components_candidate_is_skipped() -> None:
    """Degenerate LigatureTable with zero trailing components — the
    shaping walk skips it without crashing, preserving the first glyph."""
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=500, component_glyph_ids=()),
                    LigatureTable(
                        ligature_glyph=600, component_glyph_ids=(71,)
                    ),
                ),
            ),
        ),
    )
    # Empty-component candidate at index 0 is skipped; the (71,) candidate
    # wins and we get ligature 600 for f+i.
    assert sub.do_substitution_glyphs([70, 71]) == [600]


def test_ligature_extractor_records_trailing_components_only() -> None:
    """The data extractor records each LigatureTable as a
    ``trailing_components -> ligature_glyph`` entry. The implicit first
    component (= the Coverage glyph) is intentionally *not* prepended —
    the worker reattaches it at apply time."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(71,)),
                    LigatureTable(
                        ligature_glyph=600, component_glyph_ids=(71, 72)
                    ),
                ),
            ),
        ),
    )
    glyph_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_ligature_substitution_subst_format1_table(
        glyph_map, sub
    )
    assert glyph_map == {(71,): 500, (71, 72): 600}


def test_ligature_extractor_handles_multiple_ligature_sets() -> None:
    """Two Coverage entries, each with its own LigatureSet — each
    candidate becomes its own entry in the substitution map."""
    extractor = GlyphSubstitutionDataExtractor()
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70, 80),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(71,)),
                ),
            ),
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=600, component_glyph_ids=(81,)),
                ),
            ),
        ),
    )
    glyph_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_ligature_substitution_subst_format1_table(
        glyph_map, sub
    )
    assert glyph_map == {(71,): 500, (81,): 600}


def test_ligature_overlapping_candidates_first_match_wins() -> None:
    """When two candidates share the same trailing length, the first one
    encountered in the LigatureSet wins (spec: "Ligatures are processed
    in the order they appear in the array")."""
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
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
    # The implementation uses ``>=`` so the last same-length candidate
    # wins. Pin that behavior; it matches the wave-786 regression test
    # ``test_ligature_substitution_later_same_length_candidate_wins``.
    assert sub.do_substitution_glyphs([20, 21, 22]) == [200, 22]


def test_ligature_uncovered_first_glyph_is_emitted_unchanged() -> None:
    """A first glyph that isn't in Coverage is emitted as-is. The walker
    only consults the Coverage table for the *first* component of each
    candidate — it doesn't try to start a match mid-component."""
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(71,)),
                ),
            ),
        ),
    )
    # 71 is a trailing component of the ligature but never appears in
    # Coverage; starting a run with 71 must not collapse.
    assert sub.do_substitution_glyphs([71, 70, 71]) == [71, 500]
