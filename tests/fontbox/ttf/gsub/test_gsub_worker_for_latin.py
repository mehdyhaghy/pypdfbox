"""Tests for :class:`GsubWorkerForLatin`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import GsubData, GsubWorkerForLatin


def _build_gsub_data(
    feature_list: dict[str, dict[tuple[int, ...], tuple[int, ...]]],
) -> GsubData:
    return GsubData(language="LATIN", feature_list=feature_list)


def test_pass_through_when_no_features_supported() -> None:
    worker = GsubWorkerForLatin(_build_gsub_data({}))
    assert worker.apply_transforms([1, 2, 3]) == [1, 2, 3]


def test_applies_liga_ff() -> None:
    # 'f' (gid=70) + 'f' (gid=70) -> 'ff' ligature (gid=200).
    gd = _build_gsub_data({"liga": {(70, 70): (200,)}})
    worker = GsubWorkerForLatin(gd)
    assert worker.apply_transforms([70, 70, 71]) == [200, 71]


def test_applies_three_glyph_liga_ffi() -> None:
    # 'f' + 'f' + 'i' -> 'ffi' ligature.
    gd = _build_gsub_data({"liga": {(70, 70, 73): (300,)}})
    worker = GsubWorkerForLatin(gd)
    assert worker.apply_transforms([70, 70, 73]) == [300]


def test_calt_is_not_applied_for_latin() -> None:
    # The Latin worker only applies ccmp/liga/clig — calt should be ignored.
    gd = _build_gsub_data({"calt": {(1, 2): (9,)}})
    worker = GsubWorkerForLatin(gd)
    assert worker.apply_transforms([1, 2]) == [1, 2]


def test_ccmp_then_liga_chained() -> None:
    # ccmp transforms then liga collapses.
    gd = _build_gsub_data(
        {
            "ccmp": {(11,): (12,)},  # noqa
            "liga": {(12, 13): (99,)},
        }
    )
    # ccmp single-glyph -> single-glyph still requires the input chunk
    # to be a key; (11,) -> (12,) is a single-glyph substitution.
    worker = GsubWorkerForLatin(gd)
    assert worker.apply_transforms([11, 13]) == [99]


def test_empty_input() -> None:
    worker = GsubWorkerForLatin(_build_gsub_data({"liga": {(1, 2): (3,)}}))
    assert worker.apply_transforms([]) == []
