"""Hand-written tests for :class:`GlyphArraySplitterRegexImpl`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import GlyphArraySplitterRegexImpl


def test_split_no_matches_returns_input_unchanged() -> None:
    splitter = GlyphArraySplitterRegexImpl({(201, 202)})
    assert splitter.split([100, 101, 102]) == [[100, 101, 102]]


def test_split_with_match_in_the_middle() -> None:
    matchers = [[67, 112, 96], [74, 112, 76]]
    splitter = GlyphArraySplitterRegexImpl(matchers)
    assert splitter.split([94, 67, 112, 96, 112, 91, 103]) == [
        [94],
        [67, 112, 96],
        [112, 91, 103],
    ]


def test_split_prefers_longest_match() -> None:
    """Upstream's comparator sorts matchers by descending length, so the
    longer pattern must win when both could fire at the same offset."""
    splitter = GlyphArraySplitterRegexImpl([[100, 101, 102], [101, 102]])
    assert splitter.split([100, 101, 102, 103, 104]) == [
        [100, 101, 102],
        [103, 104],
    ]
