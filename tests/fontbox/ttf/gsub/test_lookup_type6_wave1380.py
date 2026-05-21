"""Wave 1380 hand-written tests for GSUB lookup Type 6 (chained contextual).

Type 6 extends Type 5 with backtrack + lookahead sequences — the most
useful contextual lookup family in real-world fonts (it drives Indic
shaping, Arabic linking, finals/initials/medials, etc.). Three subtable
formats — simple glyph contexts, class-based, full Coverage — mirror
Type 5's structure.
"""

from __future__ import annotations

import logging

from pypdfbox.fontbox.ttf.gsub import (
    ChainedClassRule,
    ChainedClassRuleSet,
    ChainedSequenceRule,
    ChainedSequenceRuleSet,
    ClassDefinitionTable,
    LookupTypeChainedContextualSubstitutionFormat1,
    LookupTypeChainedContextualSubstitutionFormat2,
    LookupTypeChainedContextualSubstitutionFormat3,
    SubstitutionLookupRecord,
)
from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)

# --------------------------------------------------------------------------
# Format 1 — chained simple glyph contexts.
# --------------------------------------------------------------------------


def test_type6_format1_full_chain_matches() -> None:
    """Backtrack [B] · Input [I I I] · Lookahead [L] — full chain matches."""
    rule = ChainedSequenceRule(
        backtrack_sequence=(5,),  # reversed order in storage
        input_sequence=(11, 12),  # trailing input (first is implicit/Coverage)
        lookahead_sequence=(20,),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=0, lookup_list_index=4),
        ),
    )
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=(rule,)),
        ),
    )
    glyphs = [5, 10, 11, 12, 20, 99]
    assert sub.match_rule(glyphs, 1) is rule


def test_type6_format1_backtrack_is_reversed_in_storage() -> None:
    """``backtrack_sequence[0]`` is the glyph immediately *before* the
    first input glyph; ``[1]`` is the one before that, etc."""
    rule = ChainedSequenceRule(
        backtrack_sequence=(7, 8),  # so the run must be ... 8, 7, <first input>
        input_sequence=(),
        lookahead_sequence=(),
    )
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=(rule,)),
        ),
    )
    assert sub.match_rule([8, 7, 10], 2) is rule
    # Reversing the backtrack order in the run breaks the match.
    assert sub.match_rule([7, 8, 10], 2) is None


def test_type6_format1_backtrack_underrun_misses() -> None:
    """Run too short on the backtrack side."""
    rule = ChainedSequenceRule(
        backtrack_sequence=(5, 6),
        input_sequence=(),
        lookahead_sequence=(),
    )
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=(rule,)),
        ),
    )
    # Only one glyph before the first input — can't satisfy two-glyph
    # backtrack.
    assert sub.match_rule([5, 10], 1) is None


def test_type6_format1_lookahead_overrun_misses() -> None:
    rule = ChainedSequenceRule(
        backtrack_sequence=(),
        input_sequence=(11,),
        lookahead_sequence=(20, 21),
    )
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=(rule,)),
        ),
    )
    # Only one glyph after the input pair — can't satisfy two-glyph
    # lookahead.
    assert sub.match_rule([10, 11, 20], 0) is None


def test_type6_format1_no_backtrack_no_lookahead_is_just_type5() -> None:
    """Empty backtrack + empty lookahead reduces Type 6 to Type 5."""
    rule = ChainedSequenceRule(
        backtrack_sequence=(),
        input_sequence=(11, 12),
        lookahead_sequence=(),
    )
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=(rule,)),
        ),
    )
    assert sub.match_rule([10, 11, 12], 0) is rule


def test_type6_format1_first_match_wins() -> None:
    """Preference order: first rule in RuleSet that matches wins."""
    initial = ChainedSequenceRule(
        backtrack_sequence=(),
        input_sequence=(),
        lookahead_sequence=(20, 21),
    )
    medial = ChainedSequenceRule(
        backtrack_sequence=(5,),
        input_sequence=(),
        lookahead_sequence=(20,),
    )
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=(initial, medial)),
        ),
    )
    # No backtrack — only `initial` applies.
    assert sub.match_rule([10, 20, 21], 0) is initial
    # With backtrack 5 — `initial` still tries first (no backtrack means
    # it'll match the lookahead too), but at start_index=1 (10 is the
    # input) the run has 5 before it, then 10, 20. `initial`'s lookahead
    # is (20, 21) — but only 20 follows. `initial` fails; `medial`
    # matches.
    assert sub.match_rule([5, 10, 20, 99], 1) is medial


def test_type6_format1_coverage_miss_returns_none() -> None:
    rule = ChainedSequenceRule(input_sequence=())
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=(rule,)),
        ),
    )
    assert sub.match_rule([99], 0) is None


def test_type6_format1_null_rule_set_skipped() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10, 20),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(
                chained_sequence_rules=(
                    ChainedSequenceRule(input_sequence=()),
                )
            ),
            None,
        ),
    )
    assert sub.match_rule([10], 0) is not None
    assert sub.match_rule([20], 0) is None


def test_type6_format1_do_substitution_raises() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(chained_sequence_rules=()),
        ),
    )
    try:
        sub.do_substitution(10, 0)
    except TypeError as exc:
        assert "chained" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("do_substitution must raise TypeError")


# --------------------------------------------------------------------------
# Format 2 — chained class-based contexts.
# --------------------------------------------------------------------------


def test_type6_format2_class_based_chain_matches() -> None:
    backtrack_cd = ClassDefinitionTable(glyph_to_class=((5, 1),))
    input_cd = ClassDefinitionTable(glyph_to_class=((10, 2), (11, 3)))
    lookahead_cd = ClassDefinitionTable(glyph_to_class=((20, 4),))

    rule = ChainedClassRule(
        backtrack_classes=(1,),
        input_classes=(3,),
        lookahead_classes=(4,),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=0, lookup_list_index=1),
        ),
    )
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        backtrack_class_definition=backtrack_cd,
        input_class_definition=input_cd,
        lookahead_class_definition=lookahead_cd,
        chained_class_rule_sets=(
            None,
            None,
            ChainedClassRuleSet(chained_class_rules=(rule,)),  # class 2
        ),
    )
    assert sub.match_rule([5, 10, 11, 20], 1) is rule


def test_type6_format2_class_based_chain_partial_failure() -> None:
    backtrack_cd = ClassDefinitionTable(glyph_to_class=((5, 1),))
    input_cd = ClassDefinitionTable(glyph_to_class=((10, 2),))
    lookahead_cd = ClassDefinitionTable(glyph_to_class=((20, 9),))  # not 4

    rule = ChainedClassRule(
        backtrack_classes=(1,),
        input_classes=(),
        lookahead_classes=(4,),
    )
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        backtrack_class_definition=backtrack_cd,
        input_class_definition=input_cd,
        lookahead_class_definition=lookahead_cd,
        chained_class_rule_sets=(None, None, ChainedClassRuleSet(
            chained_class_rules=(rule,)
        )),
    )
    # Lookahead class mismatch.
    assert sub.match_rule([5, 10, 20], 1) is None


def test_type6_format2_coverage_miss_returns_none() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        chained_class_rule_sets=(ChainedClassRuleSet(chained_class_rules=()),),
    )
    assert sub.match_rule([99], 0) is None


def test_type6_format2_class_index_out_of_range() -> None:
    input_cd = ClassDefinitionTable(glyph_to_class=((10, 99),))
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=input_cd,
        chained_class_rule_sets=(None, None),  # class 99 is OOB
    )
    assert sub.match_rule([10], 0) is None


# --------------------------------------------------------------------------
# Format 3 — chained per-position Coverage.
# --------------------------------------------------------------------------


def test_type6_format3_full_chain_matches() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        backtrack_coverages=((5, 6), (7,)),
        input_coverages=((10, 11), (20,)),
        lookahead_coverages=((30, 31),),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=0, lookup_list_index=9),
        ),
    )
    # Run laid out as: ... 7, 6, 11, 20, 30. start_index = 2.
    # Backtrack (reverse): [0]=glyph at idx 1 = 6 (in {5,6}); [1]=glyph at
    # idx 0 = 7 (in {7,}). Pass.
    # Input: idx 2 = 11 (in {10,11}); idx 3 = 20 (in {20,}). Pass.
    # Lookahead: idx 4 = 30 (in {30, 31}). Pass.
    assert sub.matches([7, 6, 11, 20, 30], 2) is True


def test_type6_format3_backtrack_position_miss() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        backtrack_coverages=((5,),),
        input_coverages=((10,),),
    )
    # Backtrack expects 5, but the preceding glyph is 99.
    assert sub.matches([99, 10], 1) is False


def test_type6_format3_run_off_start_safe() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        backtrack_coverages=((5,), (6,)),
        input_coverages=((10,),),
    )
    # Not enough room before the input for the 2-glyph backtrack.
    assert sub.matches([5, 10], 1) is False


def test_type6_format3_run_off_end_safe() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        input_coverages=((10,),),
        lookahead_coverages=((20,), (21,)),
    )
    # Only one glyph after input — can't satisfy two-glyph lookahead.
    assert sub.matches([10, 20], 0) is False


def test_type6_format3_negative_start_index_safe() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        input_coverages=((10,),),
    )
    assert sub.matches([10], -1) is False


def test_type6_format3_empty_chain_matches() -> None:
    """A fully empty chained Format 3 always matches — degenerate but
    spec-legal."""
    sub = LookupTypeChainedContextualSubstitutionFormat3()
    assert sub.matches([1, 2, 3], 0) is True


def test_type6_format3_base_coverage_first_input() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        backtrack_coverages=((5,),),
        input_coverages=((10, 11), (20,)),
        lookahead_coverages=((30,),),
    )
    assert sub.get_coverage_table() == (10, 11)


def test_type6_format3_do_substitution_raises() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        input_coverages=((10,),),
    )
    try:
        sub.do_substitution(10, 0)
    except TypeError as exc:
        assert "chained" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("do_substitution must raise TypeError")


# --------------------------------------------------------------------------
# Extractor dispatch — Type 6 lookups are skipped (logged) in
# ``MapBackedGsubData`` projection just like Type 5.
# --------------------------------------------------------------------------


def test_extractor_skips_type6_format3_with_debug_log(caplog) -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        input_coverages=((10,),),
    )

    class _StubLookup:
        def get_sub_tables(self) -> list[object]:
            return [sub]

    extractor = GlyphSubstitutionDataExtractor()
    glyph_map: dict[tuple[int, ...], int] = {}
    with caplog.at_level(
        logging.DEBUG,
        logger="pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor",
    ):
        extractor.extract_data(glyph_map, _StubLookup())

    assert glyph_map == {}
    assert any(
        "Contextual lookup" in record.getMessage()
        and "LookupTypeChainedContextualSubstitutionFormat3"
        in record.getMessage()
        for record in caplog.records
    )
