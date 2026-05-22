"""Wave 1384 — end-to-end application tests for GSUB lookup Types 5 / 6 / 7 / 8.

Wave 1380 shipped the data-class plumbing for context-aware GSUB
lookups (Types 5, 6, 7, 8) but the actual substitution surface was
inert — every contextual subtable's ``do_substitution`` raised
``TypeError`` because the single-glyph-in / single-glyph-out signature
can't express nested-lookup fan-out. Wave 1384 adds a new
:meth:`LookupSubTable.apply` contract and the
:func:`apply_lookup_table` driver, so contextual lookups now actually
fire their inner ``SubstitutionLookupRecord``s against the LookupList.

These tests synthesise minimal GSUB graphs — no font fixture needed —
and pin the matched-rule-dispatches-inner-lookup behaviour for each
subtable format.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import (
    ChainedClassRule,
    ChainedClassRuleSet,
    ChainedSequenceRule,
    ChainedSequenceRuleSet,
    ClassDefinitionTable,
    ClassRule,
    ClassRuleSet,
    LigatureSetTable,
    LigatureTable,
    LookupTable,
    LookupTypeChainedContextualSubstitutionFormat1,
    LookupTypeChainedContextualSubstitutionFormat2,
    LookupTypeChainedContextualSubstitutionFormat3,
    LookupTypeContextualSubstitutionFormat1,
    LookupTypeContextualSubstitutionFormat2,
    LookupTypeContextualSubstitutionFormat3,
    LookupTypeExtensionSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeMultipleSubstitutionFormat1,
    LookupTypeReverseChainedContextualSubstitutionFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
    SequenceRule,
    SequenceRuleSet,
    SequenceTable,
    SubstitutionLookupRecord,
    apply_lookup_table,
)

# ---------------------------------------------------------------------------
# Type 1 / 2 / 4 sanity for the new apply contract (used by Types 5/6/7/8)
# ---------------------------------------------------------------------------


def test_type1_format1_apply_substitutes_one_glyph_in_place() -> None:
    inner = LookupTypeSingleSubstFormat1(delta_glyph_id=100, coverage_table=(10,))
    glyphs = [10, 20]
    consumed = inner.apply(glyphs, 0, [])
    assert consumed == 1
    assert glyphs == [110, 20]


def test_type1_format1_apply_no_match_returns_zero() -> None:
    inner = LookupTypeSingleSubstFormat1(delta_glyph_id=100, coverage_table=(10,))
    glyphs = [99, 20]
    assert inner.apply(glyphs, 0, []) == 0
    assert glyphs == [99, 20]  # unchanged


def test_type2_apply_replaces_one_glyph_with_sequence_in_place() -> None:
    inner = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10,),
        sequence_tables=(
            SequenceTable(glyph_count=3, substitute_glyph_ids=(110, 120, 130)),
        ),
    )
    glyphs = [10, 20]
    consumed = inner.apply(glyphs, 0, [])
    assert consumed == 1
    assert glyphs == [110, 120, 130, 20]


def test_type4_apply_collapses_matched_glyphs() -> None:
    inner = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(10,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(
                        ligature_glyph=500,
                        component_glyph_ids=(20, 30),
                    ),
                ),
            ),
        ),
    )
    glyphs = [10, 20, 30, 40]
    consumed = inner.apply(glyphs, 0, [])
    assert consumed == 3
    assert glyphs == [500, 40]


# ---------------------------------------------------------------------------
# Type 5 Format 1 — simple-glyph contextual triggers inner Type 1 lookup
# ---------------------------------------------------------------------------


def test_type5_format1_dispatches_inner_type1_lookup_at_position_zero() -> None:
    """Synth a Type-5 Format-1 rule that matches `[10, 11]` and triggers
    a Type-1 inner lookup at sequence_index=0 (substitute 10 -> 110)."""
    inner_subtable = LookupTypeSingleSubstFormat1(
        delta_glyph_id=100,
        coverage_table=(10,),
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_subtable,))
    contextual_subtable = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(
                    SequenceRule(
                        input_sequence=(11,),
                        substitution_lookup_records=(
                            SubstitutionLookupRecord(
                                sequence_index=0, lookup_list_index=0
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=5, sub_tables=(contextual_subtable,)
    )
    all_lookups = (inner_lookup, contextual_lookup)
    glyphs = [10, 11, 99]
    apply_lookup_table(glyphs, contextual_lookup, all_lookups)
    assert glyphs == [110, 11, 99]


def test_type5_format1_no_match_leaves_glyph_run_unchanged() -> None:
    inner_subtable = LookupTypeSingleSubstFormat1(
        delta_glyph_id=100, coverage_table=(10,)
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_subtable,))
    contextual_subtable = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(
                    SequenceRule(
                        input_sequence=(11, 12),
                        substitution_lookup_records=(
                            SubstitutionLookupRecord(
                                sequence_index=1, lookup_list_index=0
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=5, sub_tables=(contextual_subtable,)
    )
    glyphs = [10, 11, 99]  # missing 12 — rule won't match
    apply_lookup_table(glyphs, contextual_lookup, (inner_lookup, contextual_lookup))
    assert glyphs == [10, 11, 99]


# ---------------------------------------------------------------------------
# Type 5 Format 2 — class-based contextual rule
# ---------------------------------------------------------------------------


def test_type5_format2_class_based_rule_triggers_inner_lookup() -> None:
    """Three classes (1, 2, 3); a rule on class-1 first glyph that
    needs `[class_2, class_3]` trailing and dispatches an inner Type-1
    at sequence_index=2."""
    # Inner Type-1 — substitute 13 -> 213 (delta=200).
    inner_subtable = LookupTypeSingleSubstFormat1(
        delta_glyph_id=200, coverage_table=(13,)
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_subtable,))
    class_def = ClassDefinitionTable(
        glyph_to_class=((10, 1), (11, 2), (12, 2), (13, 3))
    )
    rule = ClassRule(
        input_classes=(2, 3),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=2, lookup_list_index=0),
        ),
    )
    contextual_subtable = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=class_def,
        class_rule_sets=(
            None,
            ClassRuleSet(class_rules=(rule,)),
            None,
            None,
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=5, sub_tables=(contextual_subtable,)
    )
    glyphs = [10, 11, 13, 99]
    apply_lookup_table(glyphs, contextual_lookup, (inner_lookup, contextual_lookup))
    # Position 2 (= start + sequence_index=2) is 13; inner replaces -> 213.
    assert glyphs == [10, 11, 213, 99]


# ---------------------------------------------------------------------------
# Type 5 Format 3 — per-position coverage
# ---------------------------------------------------------------------------


def test_type5_format3_per_position_coverage_dispatches_inner_lookup() -> None:
    """Input coverage chain: pos0 in {10,11}, pos1 in {20,21}; the rule
    dispatches an inner Type-1 at sequence_index=1 (replaces 20 or 21
    by adding 100)."""
    inner_subtable = LookupTypeSingleSubstFormat1(
        delta_glyph_id=100, coverage_table=(20, 21)
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_subtable,))
    contextual_subtable = LookupTypeContextualSubstitutionFormat3(
        input_coverages=((10, 11), (20, 21)),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=1, lookup_list_index=0),
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=5, sub_tables=(contextual_subtable,)
    )
    glyphs = [11, 21, 99]
    apply_lookup_table(glyphs, contextual_lookup, (inner_lookup, contextual_lookup))
    assert glyphs == [11, 121, 99]


# ---------------------------------------------------------------------------
# Type 6 — chained contextual (backtrack + input + lookahead)
# ---------------------------------------------------------------------------


def test_type6_chained_format1_dispatches_inner_lookup_at_position_one() -> None:
    """Backtrack=[5], input=[10,11], lookahead=[20]; rule fires inner
    Type-1 (delta=100) at sequence_index=1."""
    inner_subtable = LookupTypeSingleSubstFormat1(
        delta_glyph_id=100, coverage_table=(11,)
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_subtable,))
    rule = ChainedSequenceRule(
        backtrack_sequence=(5,),
        input_sequence=(11,),
        lookahead_sequence=(20,),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=1, lookup_list_index=0),
        ),
    )
    contextual_subtable = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=(rule,)),
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=6, sub_tables=(contextual_subtable,)
    )
    glyphs = [5, 10, 11, 20, 99]
    apply_lookup_table(glyphs, contextual_lookup, (inner_lookup, contextual_lookup))
    # Position start=1 (the 10); seq_index=1 -> position 2 (the 11).
    # Inner adds 100 -> 111.
    assert glyphs == [5, 10, 111, 20, 99]


def test_type6_chained_format1_backtrack_mismatch_no_substitution() -> None:
    inner_subtable = LookupTypeSingleSubstFormat1(
        delta_glyph_id=100, coverage_table=(11,)
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_subtable,))
    rule = ChainedSequenceRule(
        backtrack_sequence=(5,),
        input_sequence=(11,),
        lookahead_sequence=(20,),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=1, lookup_list_index=0),
        ),
    )
    contextual_subtable = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=(rule,)),
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=6, sub_tables=(contextual_subtable,)
    )
    glyphs = [7, 10, 11, 20]  # backtrack=7, not 5 — no match
    apply_lookup_table(glyphs, contextual_lookup, (inner_lookup, contextual_lookup))
    assert glyphs == [7, 10, 11, 20]


def test_type6_chained_format2_class_based() -> None:
    """Backtrack class {5:cls1}, input class {10:cls1,11:cls2},
    lookahead class {20:cls1}. Rule fires inner Type-1 at seq_index=0."""
    backtrack_def = ClassDefinitionTable(glyph_to_class=((5, 1),))
    input_def = ClassDefinitionTable(glyph_to_class=((10, 1), (11, 2)))
    lookahead_def = ClassDefinitionTable(glyph_to_class=((20, 1),))
    inner_subtable = LookupTypeSingleSubstFormat1(
        delta_glyph_id=100, coverage_table=(10,)
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_subtable,))
    rule = ChainedClassRule(
        backtrack_classes=(1,),
        input_classes=(2,),
        lookahead_classes=(1,),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=0, lookup_list_index=0),
        ),
    )
    contextual_subtable = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        backtrack_class_definition=backtrack_def,
        input_class_definition=input_def,
        lookahead_class_definition=lookahead_def,
        chained_class_rule_sets=(
            None,
            ChainedClassRuleSet(chained_class_rules=(rule,)),
            None,
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=6, sub_tables=(contextual_subtable,)
    )
    glyphs = [5, 10, 11, 20]
    apply_lookup_table(glyphs, contextual_lookup, (inner_lookup, contextual_lookup))
    # Position 1 (the 10) is replaced -> 110.
    assert glyphs == [5, 110, 11, 20]


def test_type6_chained_format3_per_position_coverage() -> None:
    inner_subtable = LookupTypeSingleSubstFormat1(
        delta_glyph_id=100, coverage_table=(11,)
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_subtable,))
    contextual_subtable = LookupTypeChainedContextualSubstitutionFormat3(
        backtrack_coverages=((5, 6),),
        input_coverages=((10, 11),),
        lookahead_coverages=((20, 21),),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=0, lookup_list_index=0),
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=6, sub_tables=(contextual_subtable,)
    )
    glyphs = [6, 11, 21, 99]
    apply_lookup_table(glyphs, contextual_lookup, (inner_lookup, contextual_lookup))
    # 11 at position 1 is in input cov; inner replaces -> 111.
    assert glyphs == [6, 111, 21, 99]


# ---------------------------------------------------------------------------
# Type 7 — extension wraps Type 4 ligature
# ---------------------------------------------------------------------------


def test_type7_extension_wrapping_type4_ligature_collapses_run() -> None:
    inner_subtable = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(40,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(
                        ligature_glyph=400,
                        component_glyph_ids=(41, 42),
                    ),
                ),
            ),
        ),
    )
    extension = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=4,
        extension_offset=0x10000,
        inner_subtable=inner_subtable,
    )
    extension_lookup = LookupTable(lookup_type=7, sub_tables=(extension,))
    glyphs = [99, 40, 41, 42, 99]
    apply_lookup_table(glyphs, extension_lookup, (extension_lookup,))
    assert glyphs == [99, 400, 99]


def test_type7_extension_wrapping_type1_single_subst() -> None:
    inner_subtable = LookupTypeSingleSubstFormat2(
        substitute_glyph_ids=(100, 200),
        coverage_table=(10, 11),
    )
    extension = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0x20000,
        inner_subtable=inner_subtable,
    )
    extension_lookup = LookupTable(lookup_type=7, sub_tables=(extension,))
    glyphs = [10, 11, 12]
    apply_lookup_table(glyphs, extension_lookup, (extension_lookup,))
    assert glyphs == [100, 200, 12]


# ---------------------------------------------------------------------------
# Type 8 — reverse chained context (Arabic-shape simulation)
# ---------------------------------------------------------------------------


def test_type8_reverse_chained_substitutes_final_form_arabic_sim() -> None:
    """Simulate Arabic terminal-form pickup: when the input glyph is
    followed by a NON-joiner (space, GID 99), substitute its isolated
    form. RTL walk so substitutions don't cascade through each other.

    Setup: coverage = [50, 51, 52] = medial forms; substitute_glyph_ids
    = [150, 151, 152] = isolated forms; lookahead = [{99}] means "next
    glyph must be the space"; backtrack empty.
    """
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50, 51, 52),
        backtrack_coverage=(),
        lookahead_coverage=((99,),),
        substitute_glyph_ids=(150, 151, 152),
    )
    type8_lookup = LookupTable(lookup_type=8, sub_tables=(sub,))
    # 50 followed by 99 (space) -> 150 (isolated).
    # 51 followed by 52 -> stays (no space lookahead).
    # 52 followed by 99 -> 152 (isolated).
    glyphs = [50, 99, 51, 52, 99]
    apply_lookup_table(glyphs, type8_lookup, (type8_lookup,))
    assert glyphs == [150, 99, 51, 152, 99]


def test_type8_reverse_chained_walks_right_to_left_no_cascade() -> None:
    """If a substitute GID could itself satisfy a backtrack context on
    an earlier position, applying LTR would cascade. RTL prevents that.

    Setup:
      Coverage = [50]; substitute = [150]; backtrack = [{60}]; no
      lookahead. So a 50 preceded by a 60 is substituted to 150.

    With glyphs = [60, 50, 50]:
      - LTR would substitute pos 1 (preceded by 60) -> 150 first, then
        pos 2 would have 150 as its backtrack — no match (cov=60).
        So LTR result = [60, 150, 50]. Same as RTL here.
      - But if we add a cascade: glyphs = [60, 50, 50, 50] with
        backtrack = [{60, 150}] — LTR would cascade-substitute all
        positions, RTL wouldn't.
    """
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(50,),
        backtrack_coverage=((60, 150),),
        substitute_glyph_ids=(150,),
    )
    type8_lookup = LookupTable(lookup_type=8, sub_tables=(sub,))
    glyphs = [60, 50, 50, 50]
    apply_lookup_table(glyphs, type8_lookup, (type8_lookup,))
    # RTL walk: pos 3 -> backtrack[0]=50, not in {60,150}, no match.
    # pos 2 -> backtrack[0]=50, no match. pos 1 -> backtrack[0]=60,
    # match, substitute to 150. pos 0 -> not in coverage.
    assert glyphs == [60, 150, 50, 50]


def test_type8_no_lookahead_no_backtrack_acts_like_type1() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10, 11, 12),
        substitute_glyph_ids=(100, 200, 300),
    )
    type8_lookup = LookupTable(lookup_type=8, sub_tables=(sub,))
    glyphs = [10, 11, 12, 99]
    apply_lookup_table(glyphs, type8_lookup, (type8_lookup,))
    assert glyphs == [100, 200, 300, 99]


# ---------------------------------------------------------------------------
# Driver edge cases.
# ---------------------------------------------------------------------------


def test_apply_lookup_table_empty_glyph_list_is_no_op() -> None:
    inner = LookupTypeSingleSubstFormat1(delta_glyph_id=100, coverage_table=(10,))
    lookup = LookupTable(lookup_type=1, sub_tables=(inner,))
    glyphs: list[int] = []
    apply_lookup_table(glyphs, lookup, (lookup,))
    assert glyphs == []


def test_apply_lookup_table_no_subtables_is_no_op() -> None:
    lookup = LookupTable(lookup_type=1, sub_tables=())
    glyphs = [10, 11, 12]
    apply_lookup_table(glyphs, lookup, (lookup,))
    assert glyphs == [10, 11, 12]


def test_dispatch_records_skips_out_of_range_lookup_index() -> None:
    """A SubstitutionLookupRecord pointing at a lookup index past the
    LookupList must be silently skipped (defensive against malformed
    fonts), not crash."""
    contextual_subtable = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(
                    SequenceRule(
                        input_sequence=(11,),
                        substitution_lookup_records=(
                            SubstitutionLookupRecord(
                                sequence_index=0, lookup_list_index=99
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=5, sub_tables=(contextual_subtable,)
    )
    glyphs = [10, 11, 12]
    # No crash; the rule matched (so consumed=2) but the inner lookup
    # index is out of range so no glyph rewrite happens.
    apply_lookup_table(glyphs, contextual_lookup, (contextual_lookup,))
    assert glyphs == [10, 11, 12]


def test_dispatch_records_skips_negative_target_position() -> None:
    """A SubstitutionLookupRecord with a sequence_index that lands past
    the run end must be silently skipped."""
    inner_subtable = LookupTypeSingleSubstFormat1(
        delta_glyph_id=100, coverage_table=(11,)
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_subtable,))
    contextual_subtable = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(
                    SequenceRule(
                        input_sequence=(11,),
                        substitution_lookup_records=(
                            # sequence_index=99 lands past the run.
                            SubstitutionLookupRecord(
                                sequence_index=99, lookup_list_index=0
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    contextual_lookup = LookupTable(
        lookup_type=5, sub_tables=(contextual_subtable,)
    )
    glyphs = [10, 11, 12]
    apply_lookup_table(glyphs, contextual_lookup, (inner_lookup, contextual_lookup))
    assert glyphs == [10, 11, 12]
