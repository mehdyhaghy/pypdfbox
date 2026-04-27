"""Upstream-shaped tests for LookupSubTable variants.

Translated from synthetic equivalents of the assertions exercised by
``org.apache.fontbox.ttf.gsub.GsubWorkerForLatinTest`` (no standalone
upstream JUnit per subtable exists — the subtable behavior is exercised
through the worker test). We capture the same invariants here at
subtable granularity so a regression in delta arithmetic, indexed
substitution, or ligature shaping fails fast.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub import (
    LigatureSetTable,
    LigatureTable,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
)


def test_single_format1_basic_delta() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=10, coverage_table=(1, 2, 3))
    assert sub.do_substitution(1, 0) == 11
    assert sub.do_substitution(2, 1) == 12
    assert sub.do_substitution(3, 2) == 13


def test_single_format1_negative_delta() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=-1, coverage_table=(5,))
    assert sub.do_substitution(5, 0) == 4


def test_single_format1_uncovered_passthrough() -> None:
    sub = LookupTypeSingleSubstFormat1(delta_glyph_id=10, coverage_table=())
    assert sub.do_substitution(1, -1) == 1


def test_single_format2_indexed_substitute() -> None:
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(1, 2, 3),
        substitute_glyph_ids=(100, 200, 300),
    )
    assert sub.do_substitution(1, 0) == 100
    assert sub.do_substitution(2, 1) == 200
    assert sub.do_substitution(3, 2) == 300


def test_single_format2_uncovered_passthrough() -> None:
    sub = LookupTypeSingleSubstFormat2(
        coverage_table=(1,), substitute_glyph_ids=(100,)
    )
    assert sub.do_substitution(99, -1) == 99


def test_ligature_format1_single_glyph_signature_unsupported() -> None:
    sub = LookupTypeLigatureSubstitutionSubstFormat1()
    with pytest.raises(NotImplementedError):
        sub.do_substitution(1, 0)


def test_ligature_format1_replaces_run() -> None:
    # Equivalent to the GsubWorkerForLatin "f f i -> ffi" assertion.
    sub = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(70,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(
                        ligature_glyph=600, component_glyph_ids=(70, 71)
                    ),
                ),
            ),
        ),
    )
    assert sub.do_substitution_glyphs([70, 70, 71]) == [600]
