"""Wave 1391 — coverage round-out for :mod:`pypdfbox.fontbox.ttf.gsub.lookup_subtable`."""

from __future__ import annotations

import logging

import pytest

from pypdfbox.fontbox.ttf.gsub import (
    AlternateSetTable,
    ChainedClassRule,
    ChainedClassRuleSet,
    ChainedSequenceRule,
    ChainedSequenceRuleSet,
    ClassDefinitionTable,
    ClassRule,
    ClassRuleSet,
    CoverageTable,
    LigatureSetTable,
    LigatureTable,
    LookupTypeAlternateSubstitutionFormat1,
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
)
from pypdfbox.fontbox.ttf.gsub.lookup_subtable import apply_lookup_table
from pypdfbox.fontbox.ttf.gsub.lookup_table import LookupTable


class _BareSubtable(LookupTypeSingleSubstFormat1):
    """Concrete subclass exposing the base ``apply`` default (returns 0)."""

    def apply(self, glyph_ids, position, all_lookups):  # type: ignore[override]
        from pypdfbox.fontbox.ttf.gsub.lookup_subtable import LookupSubTable

        return LookupSubTable.apply(self, glyph_ids, position, all_lookups)


def test_base_apply_returns_zero_by_default() -> None:
    assert _BareSubtable(delta_glyph_id=0, coverage_table=(10,)).apply([10], 0, ()) == 0


def test_single_format1_apply_negative_position_returns_zero() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=5, coverage_table=(10,))
    glyphs = [10]
    assert sub.apply(glyphs, -1, ()) == 0
    assert glyphs == [10]


def test_single_format1_apply_position_past_end_returns_zero() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=5, coverage_table=(10,))
    assert sub.apply([10], 5, ()) == 0


def test_single_format1_apply_uncovered_returns_zero() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=5, coverage_table=(10,))
    glyphs = [99]
    assert sub.apply(glyphs, 0, ()) == 0
    assert glyphs == [99]


def test_single_format1_apply_covered_mutates_in_place() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=5, coverage_table=(10,))
    glyphs = [10]
    assert sub.apply(glyphs, 0, ()) == 1
    assert glyphs == [15]


def test_single_format2_apply_negative_position_returns_zero() -> None:
    sub = LookupTypeSingleSubstFormat2(coverage_table=(10,), substitute_glyph_ids=(20,))
    assert sub.apply([10], -1, ()) == 0


def test_single_format2_apply_position_past_end_returns_zero() -> None:
    sub = LookupTypeSingleSubstFormat2(coverage_table=(10,), substitute_glyph_ids=(20,))
    assert sub.apply([10], 99, ()) == 0


def test_single_format2_apply_uncovered_returns_zero() -> None:
    sub = LookupTypeSingleSubstFormat2(coverage_table=(10,), substitute_glyph_ids=(20,))
    assert sub.apply([99], 0, ()) == 0


def test_single_format2_apply_out_of_bounds_substitute_returns_zero() -> None:
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(10, 11), substitute_glyph_ids=(20,)
    )
    glyphs = [11]
    assert sub.apply(glyphs, 0, ()) == 0
    assert glyphs == [11]


def test_single_format2_apply_happy_path() -> None:
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(10, 11), substitute_glyph_ids=(20, 21)
    )
    glyphs = [10, 11]
    assert sub.apply(glyphs, 1, ()) == 1
    assert glyphs == [10, 21]


def test_multiple_apply_negative_position_returns_zero() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10,),
        sequence_tables=(SequenceTable(substitute_glyph_ids=(20, 21)),),
    )
    assert sub.apply([10], -1, ()) == 0


def test_multiple_apply_position_past_end_returns_zero() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10,),
        sequence_tables=(SequenceTable(substitute_glyph_ids=(20, 21)),),
    )
    assert sub.apply([10], 99, ()) == 0


def test_multiple_apply_uncovered_returns_zero() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10,),
        sequence_tables=(SequenceTable(substitute_glyph_ids=(20, 21)),),
    )
    assert sub.apply([99], 0, ()) == 0


def test_multiple_apply_out_of_bounds_sequence_returns_zero() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10, 11),
        sequence_tables=(SequenceTable(substitute_glyph_ids=(20,)),),
    )
    assert sub.apply([11], 0, ()) == 0


def test_multiple_apply_happy_path_expands_in_place() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(10,),
        sequence_tables=(SequenceTable(substitute_glyph_ids=(20, 21, 22)),),
    )
    glyphs = [9, 10, 11]
    assert sub.apply(glyphs, 1, ()) == 1
    assert glyphs == [9, 20, 21, 22, 11]


def test_alternate_apply_negative_position_returns_zero() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(10,),
        alternate_set_tables=(AlternateSetTable(alternate_glyph_ids=(11, 12)),),
    )
    assert sub.apply([10], -1, ()) == 0


def test_alternate_apply_position_past_end_returns_zero() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(10,),
        alternate_set_tables=(AlternateSetTable(alternate_glyph_ids=(11,)),),
    )
    assert sub.apply([10], 5, ()) == 0


def test_alternate_apply_uncovered_returns_zero() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(10,),
        alternate_set_tables=(AlternateSetTable(alternate_glyph_ids=(11,)),),
    )
    assert sub.apply([99], 0, ()) == 0


def test_alternate_apply_out_of_bounds_returns_zero() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(10, 11),
        alternate_set_tables=(AlternateSetTable(alternate_glyph_ids=(20,)),),
    )
    assert sub.apply([11], 0, ()) == 0


def test_alternate_apply_picks_first_differing_alternate() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(10,),
        alternate_set_tables=(AlternateSetTable(alternate_glyph_ids=(10, 99)),),
    )
    glyphs = [10]
    assert sub.apply(glyphs, 0, ()) == 1
    assert glyphs == [99]


def test_alternate_apply_no_differing_alternate_returns_zero() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(10,),
        alternate_set_tables=(AlternateSetTable(alternate_glyph_ids=(10,)),),
    )
    glyphs = [10]
    assert sub.apply(glyphs, 0, ()) == 0
    assert glyphs == [10]


def test_alternate_apply_empty_alternate_set_returns_zero() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(10,),
        alternate_set_tables=(AlternateSetTable(alternate_glyph_ids=()),),
    )
    assert sub.apply([10], 0, ()) == 0


def test_ligature_apply_negative_position_returns_zero() -> None:
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
    assert sub.apply([70, 71], -1, ()) == 0


def test_ligature_apply_position_past_end_returns_zero() -> None:
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
    assert sub.apply([70, 71], 99, ()) == 0


def test_ligature_apply_uncovered_returns_zero() -> None:
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
    assert sub.apply([99, 71], 0, ()) == 0


def test_ligature_apply_no_components_match_returns_zero() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(99,)),
                ),
            ),
        ),
    )
    glyphs = [70, 71]
    assert sub.apply(glyphs, 0, ()) == 0
    assert glyphs == [70, 71]


def test_ligature_apply_skips_too_long_candidates() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=600, component_glyph_ids=(71, 72, 73)),
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(71,)),
                ),
            ),
        ),
    )
    glyphs = [70, 71]
    assert sub.apply(glyphs, 0, ()) == 2
    assert glyphs == [500]


def test_ligature_apply_collapses_in_place_with_consumed_count() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(71, 72)),
                ),
            ),
        ),
    )
    glyphs = [70, 71, 72, 99]
    assert sub.apply(glyphs, 0, ()) == 3
    assert glyphs == [500, 99]


def test_sequence_rule_matches_negative_start_index_false() -> None:
    rule = SequenceRule(input_sequence=(11,))
    assert rule.matches([10, 11], -1) is False


def test_sequence_rule_matches_truncated_input_false() -> None:
    rule = SequenceRule(input_sequence=(11, 12))
    assert rule.matches([10, 11], 0) is False


def test_sequence_rule_glyph_count_default() -> None:
    assert SequenceRule(input_sequence=(11, 12)).get_glyph_count() == 3


def test_sequence_rule_get_input_sequence_and_records_round_trip() -> None:
    rec = SubstitutionLookupRecord(sequence_index=1, lookup_list_index=2)
    rule = SequenceRule(input_sequence=(11,), substitution_lookup_records=(rec,))
    assert rule.get_input_sequence() == (11,)
    assert rule.get_substitution_lookup_records() == (rec,)


def test_sequence_rule_set_accessors() -> None:
    rule = SequenceRule(input_sequence=(11,))
    rs = SequenceRuleSet(sequence_rules=(rule,))
    assert rs.get_sequence_rules() == (rule,)
    assert rs.get_sequence_rule_count() == 1


def _identity_subst(coverage_gid: int) -> LookupTable:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=100, coverage_table=(coverage_gid,))
    return LookupTable(lookup_type=1, sub_tables=(sub,))


def test_context_format1_apply_no_rule_match_returns_zero() -> None:
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(sequence_rules=(SequenceRule(input_sequence=(99,)),)),
        ),
    )
    assert sub.apply([10, 11], 0, [_identity_subst(10)]) == 0


def test_context_format1_apply_dispatches_nested_lookup() -> None:
    record = SubstitutionLookupRecord(sequence_index=0, lookup_list_index=0)
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(
                    SequenceRule(
                        input_sequence=(11,),
                        substitution_lookup_records=(record,),
                    ),
                ),
            ),
        ),
    )
    glyphs = [10, 11]
    assert sub.apply(glyphs, 0, [_identity_subst(10)]) == 2
    assert glyphs == [110, 11]


def test_context_format1_match_rule_uncovered_returns_none() -> None:
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,), sequence_rule_sets=(SequenceRuleSet(sequence_rules=()),)
    )
    assert sub.match_rule([99], 0) is None


def test_context_format1_match_rule_no_rule_set_returns_none() -> None:
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,), sequence_rule_sets=(None,)
    )
    assert sub.match_rule([10], 0) is None


def test_context_format1_match_rule_negative_start_returns_none() -> None:
    sub = LookupTypeContextualSubstitutionFormat1(coverage_table=(10,))
    assert sub.match_rule([10], -1) is None


def test_context_format1_do_substitution_raises_type_error() -> None:
    sub = LookupTypeContextualSubstitutionFormat1()
    with pytest.raises(TypeError):
        sub.do_substitution(1, 0)


def test_context_format1_accessors() -> None:
    rs = SequenceRuleSet(sequence_rules=())
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,), sequence_rule_sets=(rs,)
    )
    assert sub.get_coverage_table() == (10,)
    assert sub.get_sequence_rule_sets() == (rs,)


def test_context_format2_apply_no_match_returns_zero() -> None:
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=ClassDefinitionTable(glyph_to_class=((10, 1),)),
        class_rule_sets=(
            None,
            ClassRuleSet(class_rules=(ClassRule(input_classes=(99,)),)),
        ),
    )
    assert sub.apply([10, 11], 0, ()) == 0


def test_context_format2_apply_uncovered_first_glyph_returns_zero() -> None:
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=ClassDefinitionTable(glyph_to_class=((10, 1),)),
        class_rule_sets=(None, ClassRuleSet(class_rules=(ClassRule(),))),
    )
    assert sub.apply([99], 0, ()) == 0


def test_context_format2_apply_class_out_of_range_returns_zero() -> None:
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=ClassDefinitionTable(glyph_to_class=((10, 5),)),
        class_rule_sets=(None, None),
    )
    assert sub.apply([10], 0, ()) == 0


def test_context_format2_apply_none_rule_set_returns_zero() -> None:
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        class_rule_sets=(None,),
    )
    assert sub.apply([10], 0, ()) == 0


def test_context_format2_apply_dispatches_nested_lookup() -> None:
    record = SubstitutionLookupRecord(sequence_index=0, lookup_list_index=0)
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=ClassDefinitionTable(glyph_to_class=((10, 1), (11, 2))),
        class_rule_sets=(
            None,
            ClassRuleSet(
                class_rules=(
                    ClassRule(
                        input_classes=(2,),
                        substitution_lookup_records=(record,),
                    ),
                ),
            ),
        ),
    )
    glyphs = [10, 11]
    assert sub.apply(glyphs, 0, [_identity_subst(10)]) == 2
    assert glyphs == [110, 11]


def test_context_format2_negative_start_returns_none() -> None:
    sub = LookupTypeContextualSubstitutionFormat2(coverage_table=(10,))
    assert sub.match_rule([10], -1) is None


def test_context_format2_do_substitution_raises_type_error() -> None:
    sub = LookupTypeContextualSubstitutionFormat2()
    with pytest.raises(TypeError):
        sub.do_substitution(1, 0)


def test_context_format2_accessors() -> None:
    cdef = ClassDefinitionTable(glyph_to_class=((10, 1),))
    rs = ClassRuleSet(class_rules=())
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,), class_definition=cdef, class_rule_sets=(rs,)
    )
    assert sub.get_coverage_table() == (10,)
    assert sub.get_class_definition() is cdef
    assert sub.get_class_rule_sets() == (rs,)


def test_class_rule_accessors() -> None:
    rec = SubstitutionLookupRecord()
    rule = ClassRule(input_classes=(1, 2), substitution_lookup_records=(rec,))
    assert rule.get_input_classes() == (1, 2)
    assert rule.get_substitution_lookup_records() == (rec,)
    assert rule.get_glyph_count() == 3


def test_class_rule_set_accessor() -> None:
    rule = ClassRule()
    rs = ClassRuleSet(class_rules=(rule,))
    assert rs.get_class_rules() == (rule,)


def test_class_definition_default_class_is_zero() -> None:
    cdef = ClassDefinitionTable(glyph_to_class=((10, 5),))
    assert cdef.get_class(10) == 5
    assert cdef.get_class(99) == 0


def test_context_format3_apply_match_dispatches_records() -> None:
    record = SubstitutionLookupRecord(sequence_index=0, lookup_list_index=0)
    sub = LookupTypeContextualSubstitutionFormat3(
        input_coverages=((10,), (11,)),
        substitution_lookup_records=(record,),
    )
    glyphs = [10, 11]
    assert sub.apply(glyphs, 0, [_identity_subst(10)]) == 2
    assert glyphs == [110, 11]


def test_context_format3_apply_no_match_returns_zero() -> None:
    sub = LookupTypeContextualSubstitutionFormat3(input_coverages=((10,), (99,)))
    assert sub.apply([10, 11], 0, ()) == 0


def test_context_format3_matches_negative_start_returns_false() -> None:
    sub = LookupTypeContextualSubstitutionFormat3(input_coverages=((10,),))
    assert sub.matches([10], -1) is False


def test_context_format3_matches_truncated_input_returns_false() -> None:
    sub = LookupTypeContextualSubstitutionFormat3(input_coverages=((10,), (11,)))
    assert sub.matches([10], 0) is False


def test_context_format3_get_coverage_table_first_position() -> None:
    sub = LookupTypeContextualSubstitutionFormat3(input_coverages=((10, 11), (20,)))
    assert sub.get_coverage_table() == (10, 11)


def test_context_format3_get_coverage_table_empty_when_no_input() -> None:
    assert LookupTypeContextualSubstitutionFormat3().get_coverage_table() == ()


def test_context_format3_do_substitution_raises_type_error() -> None:
    sub = LookupTypeContextualSubstitutionFormat3()
    with pytest.raises(TypeError):
        sub.do_substitution(1, 0)


def test_context_format3_accessors() -> None:
    rec = SubstitutionLookupRecord()
    sub = LookupTypeContextualSubstitutionFormat3(
        input_coverages=((10,),), substitution_lookup_records=(rec,)
    )
    assert sub.get_input_coverages() == ((10,),)
    assert sub.get_substitution_lookup_records() == (rec,)


def test_chained_sequence_rule_accessors() -> None:
    rec = SubstitutionLookupRecord()
    rule = ChainedSequenceRule(
        backtrack_sequence=(5,),
        input_sequence=(11,),
        lookahead_sequence=(12,),
        substitution_lookup_records=(rec,),
    )
    assert rule.get_backtrack_sequence() == (5,)
    assert rule.get_input_sequence() == (11,)
    assert rule.get_lookahead_sequence() == (12,)
    assert rule.get_substitution_lookup_records() == (rec,)


def test_chained_sequence_rule_matches_negative_start_false() -> None:
    assert ChainedSequenceRule().matches([10], -1) is False


def test_chained_sequence_rule_matches_backtrack_too_long_false() -> None:
    rule = ChainedSequenceRule(backtrack_sequence=(5, 6, 7))
    assert rule.matches([10, 11, 12], 0) is False


def test_chained_sequence_rule_matches_backtrack_mismatch_false() -> None:
    rule = ChainedSequenceRule(backtrack_sequence=(5,))
    assert rule.matches([99, 10], 1) is False


def test_chained_sequence_rule_matches_input_truncated_false() -> None:
    rule = ChainedSequenceRule(input_sequence=(11, 12))
    assert rule.matches([10, 11], 0) is False


def test_chained_sequence_rule_matches_input_mismatch_false() -> None:
    rule = ChainedSequenceRule(input_sequence=(99,))
    assert rule.matches([10, 11], 0) is False


def test_chained_sequence_rule_matches_lookahead_truncated_false() -> None:
    rule = ChainedSequenceRule(input_sequence=(11,), lookahead_sequence=(12, 13))
    assert rule.matches([10, 11, 12], 0) is False


def test_chained_sequence_rule_matches_lookahead_mismatch_false() -> None:
    rule = ChainedSequenceRule(input_sequence=(11,), lookahead_sequence=(99,))
    assert rule.matches([10, 11, 12], 0) is False


def test_chained_sequence_rule_full_match_true() -> None:
    rule = ChainedSequenceRule(
        backtrack_sequence=(5,), input_sequence=(11,), lookahead_sequence=(12,)
    )
    assert rule.matches([5, 10, 11, 12], 1) is True


def test_chained_sequence_rule_set_accessor() -> None:
    rule = ChainedSequenceRule()
    rs = ChainedSequenceRuleSet(chained_sequence_rules=(rule,))
    assert rs.get_chained_sequence_rules() == (rule,)


def test_chained_context1_apply_no_match_returns_zero() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(
                chained_sequence_rules=(ChainedSequenceRule(input_sequence=(99,)),),
            ),
        ),
    )
    assert sub.apply([10, 11], 0, ()) == 0


def test_chained_context1_apply_dispatches_records() -> None:
    record = SubstitutionLookupRecord(sequence_index=0, lookup_list_index=0)
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        chained_sequence_rule_sets=(
            ChainedSequenceRuleSet(
                chained_sequence_rules=(
                    ChainedSequenceRule(
                        input_sequence=(11,),
                        substitution_lookup_records=(record,),
                    ),
                ),
            ),
        ),
    )
    glyphs = [10, 11]
    assert sub.apply(glyphs, 0, [_identity_subst(10)]) == 2
    assert glyphs == [110, 11]


def test_chained_context1_match_rule_negative_returns_none() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat1(coverage_table=(10,))
    assert sub.match_rule([10], -1) is None


def test_chained_context1_match_rule_uncovered_returns_none() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat1(coverage_table=(10,))
    assert sub.match_rule([99], 0) is None


def test_chained_context1_match_rule_none_rule_set_returns_none() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,), chained_sequence_rule_sets=(None,)
    )
    assert sub.match_rule([10], 0) is None


def test_chained_context1_do_substitution_raises_type_error() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat1()
    with pytest.raises(TypeError):
        sub.do_substitution(1, 0)


def test_chained_context1_accessors() -> None:
    rs = ChainedSequenceRuleSet()
    sub = LookupTypeChainedContextualSubstitutionFormat1(
        coverage_table=(10,), chained_sequence_rule_sets=(rs,)
    )
    assert sub.get_coverage_table() == (10,)
    assert sub.get_chained_sequence_rule_sets() == (rs,)


def test_chained_class_rule_accessors() -> None:
    rec = SubstitutionLookupRecord()
    rule = ChainedClassRule(
        backtrack_classes=(1,),
        input_classes=(2,),
        lookahead_classes=(3,),
        substitution_lookup_records=(rec,),
    )
    assert rule.get_backtrack_classes() == (1,)
    assert rule.get_input_classes() == (2,)
    assert rule.get_lookahead_classes() == (3,)
    assert rule.get_substitution_lookup_records() == (rec,)


def test_chained_class_rule_set_accessor() -> None:
    rule = ChainedClassRule()
    rs = ChainedClassRuleSet(chained_class_rules=(rule,))
    assert rs.get_chained_class_rules() == (rule,)


def test_chained_context2_apply_full_match_dispatches() -> None:
    record = SubstitutionLookupRecord(sequence_index=0, lookup_list_index=0)
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        backtrack_class_definition=ClassDefinitionTable(glyph_to_class=((5, 1),)),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 2), (11, 3))),
        lookahead_class_definition=ClassDefinitionTable(glyph_to_class=((12, 4),)),
        chained_class_rule_sets=(
            None,
            None,
            ChainedClassRuleSet(
                chained_class_rules=(
                    ChainedClassRule(
                        backtrack_classes=(1,),
                        input_classes=(3,),
                        lookahead_classes=(4,),
                        substitution_lookup_records=(record,),
                    ),
                ),
            ),
        ),
    )
    glyphs = [5, 10, 11, 12]
    assert sub.apply(glyphs, 1, [_identity_subst(10)]) == 2
    assert glyphs == [5, 110, 11, 12]


def test_chained_context2_apply_no_match_returns_zero() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        chained_class_rule_sets=(
            ChainedClassRuleSet(
                chained_class_rules=(ChainedClassRule(input_classes=(99,)),),
            ),
        ),
    )
    assert sub.apply([10, 11], 0, ()) == 0


def test_chained_context2_match_rule_backtrack_off_front_skips() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        chained_class_rule_sets=(
            ChainedClassRuleSet(
                chained_class_rules=(ChainedClassRule(backtrack_classes=(1, 2)),),
            ),
        ),
    )
    assert sub.match_rule([10, 11], 0) is None


def test_chained_context2_match_rule_backtrack_mismatch_skips() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        backtrack_class_definition=ClassDefinitionTable(glyph_to_class=((5, 9),)),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        chained_class_rule_sets=(
            ChainedClassRuleSet(
                chained_class_rules=(ChainedClassRule(backtrack_classes=(1,)),),
            ),
        ),
    )
    assert sub.match_rule([5, 10], 1) is None


def test_chained_context2_match_rule_input_truncated_skips() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        chained_class_rule_sets=(
            ChainedClassRuleSet(
                chained_class_rules=(ChainedClassRule(input_classes=(1, 2)),),
            ),
        ),
    )
    assert sub.match_rule([10, 99], 0) is None


def test_chained_context2_match_rule_input_class_mismatch_skips() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 0), (99, 5))),
        chained_class_rule_sets=(
            ChainedClassRuleSet(
                chained_class_rules=(ChainedClassRule(input_classes=(1,)),),
            ),
        ),
    )
    assert sub.match_rule([10, 99], 0) is None


def test_chained_context2_match_rule_lookahead_truncated_skips() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        chained_class_rule_sets=(
            ChainedClassRuleSet(
                chained_class_rules=(ChainedClassRule(lookahead_classes=(1,)),),
            ),
        ),
    )
    assert sub.match_rule([10], 0) is None


def test_chained_context2_match_rule_lookahead_mismatch_skips() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        lookahead_class_definition=ClassDefinitionTable(glyph_to_class=((11, 7),)),
        chained_class_rule_sets=(
            ChainedClassRuleSet(
                chained_class_rules=(ChainedClassRule(lookahead_classes=(1,)),),
            ),
        ),
    )
    assert sub.match_rule([10, 11], 0) is None


def test_chained_context2_match_rule_uncovered_returns_none() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(coverage_table=(10,))
    assert sub.match_rule([99], 0) is None


def test_chained_context2_match_rule_class_out_of_range_returns_none() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 5),)),
        chained_class_rule_sets=(None,),
    )
    assert sub.match_rule([10], 0) is None


def test_chained_context2_match_rule_none_rule_set_returns_none() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        chained_class_rule_sets=(None,),
    )
    assert sub.match_rule([10], 0) is None


def test_chained_context2_match_rule_negative_start_returns_none() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2(coverage_table=(10,))
    assert sub.match_rule([10], -1) is None


def test_chained_context2_do_substitution_raises_type_error() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat2()
    with pytest.raises(TypeError):
        sub.do_substitution(1, 0)


def test_chained_context2_accessors() -> None:
    bcdef = ClassDefinitionTable()
    icdef = ClassDefinitionTable()
    lcdef = ClassDefinitionTable()
    rs = ChainedClassRuleSet()
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        backtrack_class_definition=bcdef,
        input_class_definition=icdef,
        lookahead_class_definition=lcdef,
        chained_class_rule_sets=(rs,),
    )
    assert sub.get_coverage_table() == (10,)
    assert sub.get_backtrack_class_definition() is bcdef
    assert sub.get_input_class_definition() is icdef
    assert sub.get_lookahead_class_definition() is lcdef
    assert sub.get_chained_class_rule_sets() == (rs,)


def test_chained_context3_apply_full_match_dispatches_records() -> None:
    record = SubstitutionLookupRecord(sequence_index=0, lookup_list_index=0)
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        backtrack_coverages=((5,),),
        input_coverages=((10,),),
        lookahead_coverages=((11,),),
        substitution_lookup_records=(record,),
    )
    glyphs = [5, 10, 11]
    assert sub.apply(glyphs, 1, [_identity_subst(10)]) == 1
    assert glyphs == [5, 110, 11]


def test_chained_context3_matches_negative_start_false() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(input_coverages=((10,),))
    assert sub.matches([10], -1) is False


def test_chained_context3_matches_backtrack_off_front_false() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        backtrack_coverages=((5,), (6,)), input_coverages=((10,),)
    )
    assert sub.matches([10, 99], 1) is False


def test_chained_context3_matches_backtrack_mismatch_false() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        backtrack_coverages=((5,),), input_coverages=((10,),)
    )
    assert sub.matches([99, 10], 1) is False


def test_chained_context3_matches_input_truncated_false() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        input_coverages=((10,), (11,))
    )
    assert sub.matches([10], 0) is False


def test_chained_context3_matches_input_mismatch_false() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        input_coverages=((10,), (11,))
    )
    assert sub.matches([10, 99], 0) is False


def test_chained_context3_matches_lookahead_truncated_false() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        input_coverages=((10,),), lookahead_coverages=((11,), (12,))
    )
    assert sub.matches([10, 11], 0) is False


def test_chained_context3_matches_lookahead_mismatch_false() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        input_coverages=((10,),), lookahead_coverages=((11,),)
    )
    assert sub.matches([10, 99], 0) is False


def test_chained_context3_apply_no_match_returns_zero() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        input_coverages=((10,),), lookahead_coverages=((99,),)
    )
    assert sub.apply([10, 11], 0, ()) == 0


def test_chained_context3_get_coverage_table_first_position() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3(input_coverages=((10, 11),))
    assert sub.get_coverage_table() == (10, 11)


def test_chained_context3_get_coverage_table_empty() -> None:
    assert LookupTypeChainedContextualSubstitutionFormat3().get_coverage_table() == ()


def test_chained_context3_accessors() -> None:
    rec = SubstitutionLookupRecord()
    sub = LookupTypeChainedContextualSubstitutionFormat3(
        backtrack_coverages=((5,),),
        input_coverages=((10,),),
        lookahead_coverages=((11,),),
        substitution_lookup_records=(rec,),
    )
    assert sub.get_backtrack_coverages() == ((5,),)
    assert sub.get_input_coverages() == ((10,),)
    assert sub.get_lookahead_coverages() == ((11,),)
    assert sub.get_substitution_lookup_records() == (rec,)


def test_chained_context3_do_substitution_raises_type_error() -> None:
    sub = LookupTypeChainedContextualSubstitutionFormat3()
    with pytest.raises(TypeError):
        sub.do_substitution(1, 0)


def test_extension_with_inner_delegates_apply() -> None:
    inner = LookupTypeSingleSubstFormat1(delta_glyph_id=5, coverage_table=(10,))
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1, extension_offset=0, inner_subtable=inner
    )
    glyphs = [10]
    assert ext.apply(glyphs, 0, ()) == 1
    assert glyphs == [15]


def test_extension_without_inner_returns_zero() -> None:
    ext = LookupTypeExtensionSubstitutionFormat1(extension_lookup_type=1)
    assert ext.apply([10], 0, ()) == 0


def test_extension_without_inner_do_substitution_passthrough() -> None:
    ext = LookupTypeExtensionSubstitutionFormat1()
    assert ext.do_substitution(123, 0) == 123


def test_extension_with_inner_catches_type_error_passthrough() -> None:
    inner = LookupTypeLigatureSubstitutionSubstFormat1()
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=4, inner_subtable=inner
    )
    assert ext.do_substitution(99, 0) == 99


def test_extension_get_coverage_table_without_inner_returns_empty_object() -> None:
    ext = LookupTypeExtensionSubstitutionFormat1()
    assert isinstance(ext.get_coverage_table(), CoverageTable)


def test_extension_get_coverage_table_with_inner_returns_inner_coverage() -> None:
    inner = LookupTypeSingleSubstFormat1(delta_glyph_id=1, coverage_table=(10, 11))
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1, inner_subtable=inner
    )
    assert isinstance(ext.get_coverage_table(), CoverageTable)


def test_extension_self_wrap_logs_error(caplog) -> None:
    caplog.set_level(logging.ERROR)
    LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=7, extension_offset=0
    )
    assert any("wraps itself" in rec.message for rec in caplog.records)


def test_extension_accessors() -> None:
    inner = LookupTypeSingleSubstFormat1(coverage_table=(10,))
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1, extension_offset=12, inner_subtable=inner
    )
    assert ext.get_extension_lookup_type() == 1
    assert ext.get_extension_offset() == 12
    assert ext.get_inner_subtable() is inner


def test_reverse_chained_apply_negative_position_returns_zero() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(20,)
    )
    assert sub.apply([10], -1, ()) == 0


def test_reverse_chained_apply_position_past_end_returns_zero() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(20,)
    )
    assert sub.apply([10], 99, ()) == 0


def test_reverse_chained_apply_full_match_substitutes_in_place() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        backtrack_coverage=((5,),),
        lookahead_coverage=((11,),),
        substitute_glyph_ids=(99,),
    )
    glyphs = [5, 10, 11]
    assert sub.apply(glyphs, 1, ()) == 1
    assert glyphs == [5, 99, 11]


def test_reverse_chained_apply_no_match_returns_zero() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        backtrack_coverage=((99,),),
        lookahead_coverage=((11,),),
        substitute_glyph_ids=(99,),
    )
    glyphs = [5, 10, 11]
    assert sub.apply(glyphs, 1, ()) == 0
    assert glyphs == [5, 10, 11]


def test_reverse_chained_do_substitution_at_no_glyphs_returns_negative() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(99,)
    )
    assert sub.do_substitution_at([], 0) == -1


def test_reverse_chained_do_substitution_at_uncovered_input_passthrough() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(99,)
    )
    assert sub.do_substitution_at([77], 0) == 77


def test_reverse_chained_do_substitution_at_backtrack_off_front_passthrough() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        backtrack_coverage=((5,), (6,)),
        substitute_glyph_ids=(99,),
    )
    assert sub.do_substitution_at([10], 0) == 10


def test_reverse_chained_do_substitution_at_backtrack_mismatch_passthrough() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        backtrack_coverage=((5,),),
        substitute_glyph_ids=(99,),
    )
    assert sub.do_substitution_at([99, 10], 1) == 10


def test_reverse_chained_do_substitution_at_lookahead_off_end_passthrough() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        lookahead_coverage=((11,),),
        substitute_glyph_ids=(99,),
    )
    assert sub.do_substitution_at([10], 0) == 10


def test_reverse_chained_do_substitution_at_lookahead_mismatch_passthrough() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        lookahead_coverage=((11,),),
        substitute_glyph_ids=(99,),
    )
    assert sub.do_substitution_at([10, 88], 0) == 10


def test_reverse_chained_do_substitution_at_out_of_bounds_substitute_passthrough() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10, 11), substitute_glyph_ids=(99,)
    )
    assert sub.do_substitution_at([11], 0) == 11


def test_reverse_chained_apply_to_run_walks_right_to_left() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        lookahead_coverage=((11,),),
        substitute_glyph_ids=(99,),
    )
    assert sub.apply_to_run([10, 11, 10, 12]) == [99, 11, 10, 12]


def test_reverse_chained_apply_to_run_empty_input_returns_empty() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(99,)
    )
    assert sub.apply_to_run([]) == []


def test_reverse_chained_do_substitution_passthrough_negative_coverage() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(99,)
    )
    assert sub.do_substitution(10, -1) == 10


def test_reverse_chained_do_substitution_out_of_bounds_passthrough() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(99,)
    )
    assert sub.do_substitution(10, 5) == 10


def test_reverse_chained_accessors() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        backtrack_coverage=((5,),),
        lookahead_coverage=((11,),),
        substitute_glyph_ids=(99,),
    )
    assert sub.get_coverage_table() == (10,)
    assert sub.get_backtrack_coverage() == ((5,),)
    assert sub.get_lookahead_coverage() == ((11,),)
    assert sub.get_substitute_glyph_ids() == (99,)


def test_apply_lookup_table_reverse_walks_right_to_left_for_type8() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        lookahead_coverage=((11,),),
        substitute_glyph_ids=(99,),
    )
    lookup = LookupTable(lookup_type=8, sub_tables=(sub,))
    glyphs = [10, 11, 10, 12]
    apply_lookup_table(glyphs, lookup, (lookup,))
    assert glyphs == [99, 11, 10, 12]


def test_apply_lookup_table_ltr_for_non_type8() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=5, coverage_table=(10,))
    lookup = LookupTable(lookup_type=1, sub_tables=(sub,))
    glyphs = [10, 10]
    apply_lookup_table(glyphs, lookup, (lookup,))
    assert glyphs == [15, 15]


def test_apply_lookup_table_empty_input_no_op() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=5, coverage_table=(10,))
    lookup = LookupTable(lookup_type=1, sub_tables=(sub,))
    glyphs: list[int] = []
    apply_lookup_table(glyphs, lookup, (lookup,))
    assert glyphs == []


def test_apply_lookup_table_empty_subtables_no_op() -> None:
    lookup = LookupTable(lookup_type=1)
    glyphs = [10]
    apply_lookup_table(glyphs, lookup, (lookup,))
    assert glyphs == [10]


def test_get_coverage_object_returns_coverage_table_instance() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=0, coverage_table=(10,))
    cov = sub.get_coverage_object()
    assert isinstance(cov, CoverageTable)


def test_multiple_get_coverage_table_accessor() -> None:
    sub = LookupTypeMultipleSubstitutionFormat1(coverage_table=(10, 11))
    assert sub.get_coverage_table() == (10, 11)


def test_alternate_get_coverage_table_accessor() -> None:
    sub = LookupTypeAlternateSubstitutionFormat1(coverage_table=(10, 11))
    assert sub.get_coverage_table() == (10, 11)


def test_ligature_get_coverage_table_accessor() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1(coverage_table=(10,))
    assert sub.get_coverage_table() == (10,)


def test_ligature_apply_skips_empty_component_candidate() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(ligature_glyph=999, component_glyph_ids=()),
                    LigatureTable(ligature_glyph=500, component_glyph_ids=(71,)),
                ),
            ),
        ),
    )
    glyphs = [70, 71]
    assert sub.apply(glyphs, 0, ()) == 2
    assert glyphs == [500]


def test_substitution_lookup_record_accessors() -> None:
    rec = SubstitutionLookupRecord(sequence_index=3, lookup_list_index=7)
    assert rec.get_sequence_index() == 3
    assert rec.get_lookup_list_index() == 7
    s = rec.to_string()
    assert "sequenceIndex=3" in s
    assert "lookupListIndex=7" in s
    assert str(rec) == s


def test_context_format1_apply_dispatches_records_with_empty_component() -> None:
    # SequenceRule with empty input_sequence (matches the Coverage glyph alone).
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(sequence_rules=(SequenceRule(input_sequence=()),)),
        ),
    )
    assert sub.apply([10], 0, ()) == 1


def test_context_format2_apply_skips_rule_with_truncated_input() -> None:
    # The rule's input_classes extend past the end of glyph_ids → skip.
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        class_rule_sets=(
            ClassRuleSet(
                class_rules=(ClassRule(input_classes=(1, 2, 3)),),
            ),
        ),
    )
    assert sub.apply([10], 0, ()) == 0


def test_extension_to_string_includes_lookup_type() -> None:
    inner = LookupTypeSingleSubstFormat1(delta_glyph_id=1, coverage_table=(10,))
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1, extension_offset=42, inner_subtable=inner
    )
    s = ext.to_string()
    assert "extensionLookupType=1" in s
    assert "extensionOffset=42" in s
    assert str(ext) == s


def test_reverse_chained_get_substitute_glyph_i_ds_alias() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(99, 100)
    )
    assert sub.get_substitute_glyph_i_ds() == (99, 100)


def test_reverse_chained_do_substitution_at_returns_substitute_when_in_bounds() -> None:
    """When coverage_index resolves and substitute exists, return the substitute."""
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        substitute_glyph_ids=(99,),
    )
    # No backtrack / lookahead required — just covered glyph.
    assert sub.do_substitution_at([10], 0) == 99


def test_reverse_chained_to_string_includes_counts() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,),
        backtrack_coverage=((5,),),
        lookahead_coverage=((11,),),
        substitute_glyph_ids=(99,),
    )
    s = sub.to_string()
    assert "backtrackGlyphCount=1" in s
    assert "lookaheadGlyphCount=1" in s
    assert "glyphCount=1" in s
    assert str(sub) == s


def test_chained_context2_match_rule_finds_full_match() -> None:
    """Drive Format-2 match_rule through a full happy-path match."""
    record = SubstitutionLookupRecord()
    sub = LookupTypeChainedContextualSubstitutionFormat2(
        coverage_table=(10,),
        input_class_definition=ClassDefinitionTable(glyph_to_class=((10, 0),)),
        chained_class_rule_sets=(
            ChainedClassRuleSet(
                chained_class_rules=(
                    ChainedClassRule(
                        substitution_lookup_records=(record,),
                    ),
                ),
            ),
        ),
    )
    rule = sub.match_rule([10], 0)
    assert rule is not None


def test_reverse_chained_do_substitution_at_negative_position_returns_negative() -> None:
    # Non-empty glyph list with negative position — hits the `position < 0`
    # branch (line 2044-2045), returns -1.
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(99,)
    )
    assert sub.do_substitution_at([10], -1) == -1


def test_reverse_chained_do_substitution_at_position_past_end_returns_negative() -> None:
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(99,)
    )
    assert sub.do_substitution_at([10], 5) == -1


def test_dispatch_substitution_records_skips_out_of_bounds_seq_index() -> None:
    """SubstitutionLookupRecord with seq_index pointing past the input."""
    record = SubstitutionLookupRecord(sequence_index=10, lookup_list_index=0)
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(
                    SequenceRule(
                        input_sequence=(),
                        substitution_lookup_records=(record,),
                    ),
                ),
            ),
        ),
    )
    glyphs = [10]
    # Match succeeds (rule glyph_count=1 -> consumed=1) but the inner
    # dispatch silently skips the out-of-bounds record offset.
    assert sub.apply(glyphs, 0, [_identity_subst(10)]) == 1
    # The glyph wasn't modified because the nested lookup didn't fire.
    assert glyphs == [10]


def test_dispatch_substitution_records_skips_out_of_bounds_lookup_index() -> None:
    record = SubstitutionLookupRecord(sequence_index=0, lookup_list_index=99)
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(
                    SequenceRule(
                        input_sequence=(),
                        substitution_lookup_records=(record,),
                    ),
                ),
            ),
        ),
    )
    glyphs = [10]
    # Match succeeds but the dispatch silently skips the out-of-bounds
    # lookup-list index.
    assert sub.apply(glyphs, 0, [_identity_subst(10)]) == 1
    assert glyphs == [10]


def test_reverse_chained_do_substitution_returns_substitute_when_in_bounds() -> None:
    """do_substitution (no context) returns the substitute at valid coverage index."""
    sub = LookupTypeReverseChainedContextualSubstitutionFormat1(
        coverage_table=(10,), substitute_glyph_ids=(99,)
    )
    assert sub.do_substitution(10, 0) == 99
