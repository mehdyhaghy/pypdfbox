"""Wave 1380 hand-written tests for GSUB lookup Type 5 (contextual).

Type 5 substitutes glyphs based on the *context* in which they appear.
Three subtable formats — simple glyph, class-based, full Coverage —
are wired in :mod:`pypdfbox.fontbox.ttf.gsub.lookup_subtable`. The
substitution itself is delegated to nested lookups (referenced via
``SubstitutionLookupRecord``), so these tests pin the rule-matching
surface that callers (a full shaping engine) drive.
"""

from __future__ import annotations

import logging

from pypdfbox.fontbox.ttf.gsub import (
    ClassDefinitionTable,
    ClassRule,
    ClassRuleSet,
    LookupTypeContextualSubstitutionFormat1,
    LookupTypeContextualSubstitutionFormat2,
    LookupTypeContextualSubstitutionFormat3,
    SequenceRule,
    SequenceRuleSet,
    SubstitutionLookupRecord,
)
from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)

# --------------------------------------------------------------------------
# SubstitutionLookupRecord — the (sequence_index, lookup_list_index) pair.
# --------------------------------------------------------------------------


def test_substitution_lookup_record_basic_accessors() -> None:
    record = SubstitutionLookupRecord(sequence_index=2, lookup_list_index=7)
    assert record.get_sequence_index() == 2
    assert record.get_lookup_list_index() == 7
    rendered = record.to_string()
    assert "sequenceIndex=2" in rendered
    assert "lookupListIndex=7" in rendered
    # __str__ should mirror to_string for log-scraping parity.
    assert str(record) == rendered


# --------------------------------------------------------------------------
# Format 1 — simple glyph contexts (Coverage + SequenceRuleSet array).
# --------------------------------------------------------------------------


def test_type5_format1_single_rule_matches() -> None:
    """First-glyph Coverage matches and trailing input matches."""
    rule = SequenceRule(
        input_sequence=(11, 12),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=0, lookup_list_index=3),
        ),
    )
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(SequenceRuleSet(sequence_rules=(rule,)),),
    )
    matched = sub.match_rule([10, 11, 12, 99], 0)
    assert matched is rule
    assert matched.get_glyph_count() == 3  # implicit-first + two trailing


def test_type5_format1_glyph_count_includes_implicit_first() -> None:
    rule = SequenceRule(input_sequence=(20, 21, 22))
    # glyph_count defaults to len(trailing) + 1 unless explicitly set.
    assert rule.glyph_count == 4
    # Honors an explicit override (defensive against malformed fonts).
    rule_explicit = SequenceRule(input_sequence=(20, 21), glyph_count=9)
    assert rule_explicit.get_glyph_count() == 9


def test_type5_format1_first_match_wins() -> None:
    """RuleSet order is "ordered by preference" — first match wins."""
    rule_long = SequenceRule(input_sequence=(11, 12, 13))
    rule_short = SequenceRule(input_sequence=(11,))
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(sequence_rules=(rule_long, rule_short)),
        ),
    )
    # Both rules could match the trailing prefix, but rule_long is first
    # in the RuleSet so it wins.
    assert sub.match_rule([10, 11, 12, 13, 14], 0) is rule_long
    # Without the third trailing glyph rule_long can't match — the
    # second rule (rule_short) wins instead.
    assert sub.match_rule([10, 11, 99, 99], 0) is rule_short


def test_type5_format1_coverage_miss_returns_none() -> None:
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(SequenceRule(input_sequence=(11, 12)),)
            ),
        ),
    )
    # First glyph isn't covered.
    assert sub.match_rule([99, 11, 12], 0) is None


def test_type5_format1_truncated_input_misses() -> None:
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(SequenceRule(input_sequence=(11, 12, 13)),)
            ),
        ),
    )
    # Run is shorter than the rule's input sequence.
    assert sub.match_rule([10, 11], 0) is None


def test_type5_format1_null_rule_set_skipped() -> None:
    """OpenType allows null RuleSet offsets — the Coverage slot has no rules."""
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10, 20),
        sequence_rule_sets=(
            SequenceRuleSet(
                sequence_rules=(SequenceRule(input_sequence=(11,)),)
            ),
            None,  # GID 20 is covered but has no rule set.
        ),
    )
    assert sub.match_rule([10, 11], 0) is not None
    assert sub.match_rule([20, 11], 0) is None


def test_type5_format1_negative_start_index_safe() -> None:
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(
            SequenceRuleSet(sequence_rules=(SequenceRule(input_sequence=()),)),
        ),
    )
    assert sub.match_rule([10], -1) is None


def test_type5_format1_do_substitution_raises() -> None:
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(SequenceRuleSet(sequence_rules=()),),
    )
    try:
        sub.do_substitution(10, 0)
    except TypeError as exc:
        assert "contextual" in str(exc).lower()
    else:  # pragma: no cover - defensive
        raise AssertionError("do_substitution must raise TypeError")


# --------------------------------------------------------------------------
# Format 2 — class-based glyph contexts.
# --------------------------------------------------------------------------


def test_type5_format2_class_lookup_matches() -> None:
    cls_def = ClassDefinitionTable(
        glyph_to_class=((10, 1), (11, 2), (12, 2), (13, 3))
    )
    rule = ClassRule(
        input_classes=(2, 3),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=0, lookup_list_index=5),
        ),
    )
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=cls_def,
        class_rule_sets=(
            None,  # class 0
            ClassRuleSet(class_rules=(rule,)),  # class 1 — first glyph's class
            None,
            None,
        ),
    )
    assert sub.match_rule([10, 12, 13], 0) is rule


def test_type5_format2_class_lookup_no_match() -> None:
    cls_def = ClassDefinitionTable(glyph_to_class=((10, 1), (11, 2), (12, 9)))
    rule = ClassRule(input_classes=(2,))
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=cls_def,
        class_rule_sets=(None, ClassRuleSet(class_rules=(rule,))),
    )
    # 12 has class 9, not 2 — no match.
    assert sub.match_rule([10, 12], 0) is None


def test_type5_format2_default_class_is_zero() -> None:
    cls_def = ClassDefinitionTable(glyph_to_class=((10, 1),))
    # Unknown GID 11 falls into class 0.
    assert cls_def.get_class(11) == 0
    assert cls_def.get_class(10) == 1


def test_type5_format2_class_rule_set_index_out_of_range() -> None:
    cls_def = ClassDefinitionTable(glyph_to_class=((10, 5),))
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=cls_def,
        class_rule_sets=(None, None),  # only 2 entries, class 5 is OOB
    )
    assert sub.match_rule([10], 0) is None


def test_type5_format2_coverage_miss_returns_none() -> None:
    cls_def = ClassDefinitionTable(glyph_to_class=((99, 1),))
    sub = LookupTypeContextualSubstitutionFormat2(
        coverage_table=(10,),
        class_definition=cls_def,
        class_rule_sets=(
            None,
            ClassRuleSet(class_rules=(ClassRule(input_classes=()),)),
        ),
    )
    # 99 isn't in Coverage even though its class lines up.
    assert sub.match_rule([99], 0) is None


# --------------------------------------------------------------------------
# Format 3 — per-position Coverage.
# --------------------------------------------------------------------------


def test_type5_format3_full_input_coverage_matches() -> None:
    sub = LookupTypeContextualSubstitutionFormat3(
        input_coverages=((10, 11), (20, 21), (30,)),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=1, lookup_list_index=2),
        ),
    )
    assert sub.matches([11, 20, 30, 99], 0) is True
    assert sub.matches([10, 21, 30], 0) is True


def test_type5_format3_position_miss_returns_false() -> None:
    sub = LookupTypeContextualSubstitutionFormat3(
        input_coverages=((10,), (20,), (30,)),
    )
    # Middle position fails.
    assert sub.matches([10, 99, 30], 0) is False


def test_type5_format3_runs_off_end_safe() -> None:
    sub = LookupTypeContextualSubstitutionFormat3(
        input_coverages=((10,), (20,), (30,)),
    )
    assert sub.matches([10, 20], 0) is False
    # Negative start index is also safe.
    assert sub.matches([10, 20, 30], -1) is False


def test_type5_format3_base_coverage_first_position() -> None:
    """``get_coverage_table`` returns the first input Coverage so callers
    can do the cheap "is this glyph eligible?" filter that other lookup
    types use."""
    sub = LookupTypeContextualSubstitutionFormat3(
        input_coverages=((10, 11), (20, 21)),
    )
    assert sub.get_coverage_table() == (10, 11)


def test_type5_format3_empty_input_matches_anything() -> None:
    """Defensive — an empty input coverage chain is degenerate but
    shouldn't crash the matcher."""
    sub = LookupTypeContextualSubstitutionFormat3()
    assert sub.matches([], 0) is True


# --------------------------------------------------------------------------
# Extractor dispatch — Type 5 lookups should be skipped (logged) in
# ``MapBackedGsubData`` projection.
# --------------------------------------------------------------------------


def test_extractor_skips_type5_format1_with_debug_log(caplog) -> None:
    sub = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(10,),
        sequence_rule_sets=(SequenceRuleSet(sequence_rules=()),),
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
        and "LookupTypeContextualSubstitutionFormat1" in record.getMessage()
        for record in caplog.records
    )
