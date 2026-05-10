"""Tests for :class:`GsubWorkerForDflt`.

Hand-written tests — upstream's ``GsubWorkerForDfltTest`` exercises a
real Lohit-Devanagari font, which we don't ship. We instead drive the
worker with synthetic :class:`GsubData` carrying small feature tables.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import GsubData, GsubWorkerForDflt


def _build_gsub_data(
    feature_list: dict[str, dict[tuple[int, ...], tuple[int, ...]]],
) -> GsubData:
    return GsubData(language="DFLT", feature_list=feature_list)


def test_pass_through_when_no_features_supported() -> None:
    gd = _build_gsub_data({})
    worker = GsubWorkerForDflt(gd)
    assert worker.apply_transforms([1, 2, 3]) == [1, 2, 3]


def test_applies_liga_substitution() -> None:
    # liga: glyph cluster (10, 11) -> single ligature glyph 99.
    gd = _build_gsub_data({"liga": {(10, 11): (99,)}})
    worker = GsubWorkerForDflt(gd)
    assert worker.apply_transforms([5, 10, 11, 12]) == [5, 99, 12]


def test_applies_features_in_specified_order() -> None:
    # ccmp runs before liga: (1, 2) -> (3,) then (3, 4) -> (7,)
    gd = _build_gsub_data(
        {
            "ccmp": {(1, 2): (3,)},
            "liga": {(3, 4): (7,)},
        }
    )
    worker = GsubWorkerForDflt(gd)
    assert worker.apply_transforms([1, 2, 4]) == [7]


def test_empty_input_returns_empty_list() -> None:
    gd = _build_gsub_data({"liga": {(10, 11): (99,)}})
    worker = GsubWorkerForDflt(gd)
    assert worker.apply_transforms([]) == []


def test_unmatched_glyphs_pass_through() -> None:
    gd = _build_gsub_data({"liga": {(10, 11): (99,)}})
    worker = GsubWorkerForDflt(gd)
    assert worker.apply_transforms([1, 2, 3]) == [1, 2, 3]


def test_multi_glyph_substitution_skipped() -> None:
    # Substitutions whose replacement is more than one glyph are not
    # collapsed by the dflt worker (only single-glyph ligatures are).
    gd = _build_gsub_data({"liga": {(10, 11): (98, 99)}})
    worker = GsubWorkerForDflt(gd)
    assert worker.apply_transforms([10, 11]) == [10, 11]
