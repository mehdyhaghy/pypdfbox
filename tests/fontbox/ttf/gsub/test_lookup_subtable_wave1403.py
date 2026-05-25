"""Wave 1403 — branch round-out for :mod:`...gsub.lookup_subtable`.

Closes the partial arcs:

* ``[246,244]`` — ``consumed > 0`` False branch in
  :func:`_dispatch_substitution_records` (inner subtable returns 0, the
  loop advances to the next subtable).
* ``[244,235]`` — the inner-subtable ``for`` loop exhausts without a
  break and control returns to the records loop.
* ``[926,-925]`` — :meth:`LigatureSetTable.__post_init__` exit arc when
  ``ligature_count`` is already non-zero (the count-default ``if`` is
  False).
* ``[1180,-1179]`` — :meth:`ClassRule.__post_init__` exit arc when
  ``glyph_count`` is already non-zero.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import (
    ClassRule,
    LigatureSetTable,
    LookupTypeContextualSubstitutionFormat1,
    LookupTypeSingleSubstFormat1,
    SequenceRule,
    SequenceRuleSet,
    SubstitutionLookupRecord,
)
from pypdfbox.fontbox.ttf.gsub.lookup_table import LookupTable


def test_dispatch_records_inner_subtable_returns_zero() -> None:
    """A contextual rule dispatching into an inner lookup whose only
    subtable does NOT cover the target glyph returns 0 — exercising both
    the ``consumed > 0`` False arc ([246,244]) and the loop-exhaust arc
    ([244,235]).

    Context subtable covers glyph 5; the rule's lookup record points at
    inner lookup 0, a single-substitution that covers glyph 99 (not 5),
    so it consumes nothing at the target position.
    """
    inner_single = LookupTypeSingleSubstFormat1(
        delta_glyph_id=1, coverage_table=(99,)
    )
    inner_lookup = LookupTable(lookup_type=1, sub_tables=(inner_single,))
    rule = SequenceRule(
        input_sequence=(),
        substitution_lookup_records=(
            SubstitutionLookupRecord(sequence_index=0, lookup_list_index=0),
        ),
    )
    context = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(5,),
        sequence_rule_sets=(SequenceRuleSet(sequence_rules=(rule,)),),
    )
    glyph_ids = [5, 6, 7]
    consumed = context.apply(glyph_ids, 0, (inner_lookup,))
    # The rule matched (consumed == its glyph_count == 1) but the nested
    # lookup substituted nothing because glyph 5 is not covered by it.
    assert consumed == 1
    assert glyph_ids == [5, 6, 7]


def test_ligature_set_table_with_explicit_count_keeps_it() -> None:
    """An explicit non-zero ``ligature_count`` is preserved — the
    count-default ``if`` is False ([926,-925] exit arc)."""
    table = LigatureSetTable(ligature_tables=(), ligature_count=5)
    assert table.get_ligature_count() == 5


def test_class_rule_with_explicit_glyph_count_keeps_it() -> None:
    """An explicit non-zero ``glyph_count`` is preserved — the
    count-default ``if`` is False ([1180,-1179] exit arc)."""
    rule = ClassRule(input_classes=(1, 2), glyph_count=9)
    assert rule.get_glyph_count() == 9
