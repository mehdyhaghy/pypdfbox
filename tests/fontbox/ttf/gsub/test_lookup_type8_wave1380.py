"""Wave 1380 hand-written tests for GSUB lookup Type 8.

Type 8 is *Reverse Chained Contextual Single Substitution* — single
glyph substitution applied to the input glyph when its surrounding
context (backtrack + lookahead) matches a set of Coverage tables.
Applied in *reverse glyph order* (right-to-left within the run);
this matters because if a substituted glyph could itself satisfy a
backtrack context for an earlier position, the right-to-left walk
prevents cascading substitution through the just-substituted glyphs.

Real-world usage: almost exclusively Arabic + Hebrew cursive shaping
(terminal / initial / medial forms — the *next* glyph determines
which form the *current* glyph should pick up).

Tests cover:

* Single-glyph ``do_substitution`` follows the parallel
  Coverage / substitute-array contract.
* ``do_substitution_at`` end-to-end: positive context match → substitute;
  any single context mismatch → original glyph.
* Insufficient backtrack / lookahead positions (run too short for the
  configured context) → original glyph; never an out-of-bounds error.
* No backtrack / no lookahead degenerate case → behaves like a Type-1
  substitution at every covered position.
* ``apply_to_run`` walks right-to-left and emits a new list with the
  substituted glyph in place at each matching position.
* Right-to-left walk semantics: a substituted glyph at position N is
  *not* picked up by a backtrack from position M < N during the same
  ``apply_to_run`` pass (each substitution sees the ORIGINAL glyphs
  at lower indices, the SUBSTITUTED glyphs at higher indices —
  exactly the OpenType spec contract).
* :class:`GlyphSubstitutionDataExtractor` skips Type 8 lookups in
  the flat map projection (context-aware shaping cannot reduce to
  ``(input,) -> output``) — matches the Type 5 / Type 6 contract.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import (
    LookupTypeReverseChainedContextualSubstitutionFormat1,
)
from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)

# ---------- single-glyph contract -----------------------------------------


def test_reverse_chained_do_substitution_returns_substitute_at_index() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10, 11, 12),
        substitute_glyph_ids=(100, 200, 300),
    )
    assert sub.do_substitution(10, 0) == 100
    assert sub.do_substitution(11, 1) == 200
    assert sub.do_substitution(12, 2) == 300


def test_reverse_chained_do_substitution_passes_through_when_not_covered() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        substitute_glyph_ids=(100,),
    )
    # No coverage index → original passes through.
    assert sub.do_substitution(20, -1) == 20


def test_reverse_chained_do_substitution_out_of_range_passes_through() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        substitute_glyph_ids=(100,),
    )
    # Coverage index beyond substitute_glyph_ids → original.
    assert sub.do_substitution(10, 99) == 10


# ---------- context-aware substitution ------------------------------------


def test_reverse_chained_full_match_returns_substitute() -> None:
    """Arabic-style: glyph 50 ('alif initial-form trigger') is the input,
    must be preceded by glyph 49 ('lam'), and followed by glyph 51
    ('whitespace boundary'). When the context matches end-to-end, the
    input is replaced by glyph 500 (the substituted initial form)."""
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,),),  # one preceding glyph: 49
        lookahead_coverage=((51,),),  # one following glyph: 51
        substitute_glyph_ids=(500,),
    )
    # Run: [49, 50, 51], substitute at position 1.
    assert sub.do_substitution_at([49, 50, 51], 1) == 500


def test_reverse_chained_backtrack_mismatch_returns_original() -> None:
    """If the preceding glyph doesn't match the backtrack coverage,
    the input is unchanged."""
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,),),
        lookahead_coverage=((51,),),
        substitute_glyph_ids=(500,),
    )
    # Run: [99, 50, 51] — backtrack expected 49 but found 99.
    assert sub.do_substitution_at([99, 50, 51], 1) == 50


def test_reverse_chained_lookahead_mismatch_returns_original() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,),),
        lookahead_coverage=((51,),),
        substitute_glyph_ids=(500,),
    )
    # Run: [49, 50, 88] — lookahead expected 51 but found 88.
    assert sub.do_substitution_at([49, 50, 88], 1) == 50


def test_reverse_chained_main_coverage_mismatch_returns_original() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,),),
        lookahead_coverage=((51,),),
        substitute_glyph_ids=(500,),
    )
    # Input 77 is not in the main Coverage at all → original.
    assert sub.do_substitution_at([49, 77, 51], 1) == 77


def test_reverse_chained_insufficient_backtrack_returns_original() -> None:
    """If the position is too close to the start of the run to satisfy
    the backtrack count, return the original (no out-of-bounds error)."""
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,), (48,)),  # two preceding glyphs needed
        lookahead_coverage=(),
        substitute_glyph_ids=(500,),
    )
    # Position 1: only one glyph at index 0 — insufficient backtrack.
    assert sub.do_substitution_at([49, 50, 99], 1) == 50


def test_reverse_chained_insufficient_lookahead_returns_original() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=(),
        lookahead_coverage=((51,), (52,)),  # two following glyphs needed
        substitute_glyph_ids=(500,),
    )
    # Position 1 (last index): no following glyphs at all.
    assert sub.do_substitution_at([49, 50, 51], 1) == 50


def test_reverse_chained_no_context_acts_as_type1() -> None:
    """Degenerate Type-8: no backtrack, no lookahead. Behaves like a
    Type-1 single substitution at every covered position."""
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10, 11, 12),
        backtrack_coverage=(),
        lookahead_coverage=(),
        substitute_glyph_ids=(100, 200, 300),
    )
    assert sub.do_substitution_at([10, 11, 12], 0) == 100
    assert sub.do_substitution_at([10, 11, 12], 1) == 200
    assert sub.do_substitution_at([10, 11, 12], 2) == 300


def test_reverse_chained_multi_glyph_class_in_backtrack() -> None:
    """Backtrack coverage entries are *classes* — any glyph in the
    set satisfies that position. Real fonts use this to match e.g.
    'any of the Arabic letters that join from the right'."""
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49, 48, 47),),  # any of these
        lookahead_coverage=(),
        substitute_glyph_ids=(500,),
    )
    assert sub.do_substitution_at([49, 50], 1) == 500
    assert sub.do_substitution_at([48, 50], 1) == 500
    assert sub.do_substitution_at([47, 50], 1) == 500
    # Glyph 60 not in the class → no match.
    assert sub.do_substitution_at([60, 50], 1) == 50


# ---------- right-to-left run application --------------------------------


def test_apply_to_run_substitutes_at_every_match() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,),),
        lookahead_coverage=(),
        substitute_glyph_ids=(500,),
    )
    # Two independent matches in the run at positions 1 and 3.
    result = sub.apply_to_run([49, 50, 49, 50])
    assert result == [49, 500, 49, 500]


def test_apply_to_run_skips_unmatched_positions() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,),),
        lookahead_coverage=(),
        substitute_glyph_ids=(500,),
    )
    # Position 1 matches; position 3 has the wrong backtrack.
    result = sub.apply_to_run([49, 50, 99, 50])
    assert result == [49, 500, 99, 50]


def test_apply_to_run_right_to_left_walk_does_not_cascade() -> None:
    """The OpenType spec requires reverse-chained lookups to be applied
    right-to-left. This matters when a substituted GID could itself
    satisfy a backtrack context for an earlier position — a left-to-right
    walk would cascade through the just-substituted glyphs (wrong);
    the right-to-left walk lets each substitution see the *original*
    glyphs to its left."""
    # Construct a subtable where:
    # - Coverage: {50}
    # - Backtrack: glyph 49 must precede
    # - Substitute: glyph 500
    # If we then have [49, 50, 49, 50], applying right-to-left:
    #   position 3: backtrack glyph at 2 is 49 → match, substitute to 500
    #     run becomes [49, 50, 49, 500]
    #   position 2: glyph 49 not in coverage → skip
    #   position 1: backtrack glyph at 0 is 49 → match, substitute to 500
    #     run becomes [49, 500, 49, 500]
    #   position 0: glyph 49 not in coverage → skip
    # Final: [49, 500, 49, 500]
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,),),
        lookahead_coverage=(),
        substitute_glyph_ids=(500,),
    )
    assert sub.apply_to_run([49, 50, 49, 50]) == [49, 500, 49, 500]


def test_apply_to_run_returns_new_list_not_input() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        substitute_glyph_ids=(500,),
    )
    run = [50, 50, 50]
    out = sub.apply_to_run(run)
    assert out == [500, 500, 500]
    # Input not mutated.
    assert run == [50, 50, 50]


def test_apply_to_run_empty_run() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        substitute_glyph_ids=(500,),
    )
    assert sub.apply_to_run([]) == []


# ---------- accessor / shape parity --------------------------------------


def test_get_substitute_glyph_i_ds_alias_returns_same_tuple() -> None:
    """Snake-case translation of upstream ``getSubstituteGlyphIDs`` —
    the underscore-separated form must alias the canonical accessor."""
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        substitute_glyph_ids=(100, 200, 300),
    )
    assert sub.get_substitute_glyph_ids() == (100, 200, 300)
    assert sub.get_substitute_glyph_i_ds() == (100, 200, 300)


def test_reverse_chained_to_string_mirrors_upstream_shape() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,), (48,)),
        lookahead_coverage=((51,),),
        substitute_glyph_ids=(500,),
    )
    text = str(sub)
    assert text.startswith("LookupTypeReverseChainedContextualSubstitutionFormat1[")
    assert "substFormat=1" in text
    assert "backtrackGlyphCount=2" in text
    assert "lookaheadGlyphCount=1" in text
    assert "glyphCount=1" in text


# ---------- extractor dispatch -------------------------------------------


def test_extractor_skips_reverse_chained_subtable_silently() -> None:
    """Reverse-chained context cannot be projected into the flat
    ``(input,) -> output`` map exposed by :class:`MapBackedGsubData`
    (the substitution depends on surrounding glyphs). The extractor
    must skip the subtable without raising or partially populating
    the map."""
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((49,),),
        substitute_glyph_ids=(500,),
    )

    class _FauxLookup:
        def get_sub_tables(self) -> list[object]:
            return [sub]

    extractor = GlyphSubstitutionDataExtractor()
    glyph_substitution_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data(glyph_substitution_map, _FauxLookup())
    assert glyph_substitution_map == {}
