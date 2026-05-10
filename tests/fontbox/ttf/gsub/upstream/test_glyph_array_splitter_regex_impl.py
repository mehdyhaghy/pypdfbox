"""Upstream-ported tests for :class:`GlyphArraySplitterRegexImpl`.

Translated from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GlyphArraySplitterRegexImplTest.java``
upstream Apache PDFBox 3.0.x.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import (
    GlyphArraySplitter,
    GlyphArraySplitterRegexImpl,
)


def test_split_1() -> None:
    matchers = [[84, 93], [102, 82], [104, 87]]
    test_class: GlyphArraySplitter = GlyphArraySplitterRegexImpl(matchers)
    glyph_ids = [84, 112, 93, 104, 82, 61, 96, 102, 93, 104, 87, 110]
    tokens = test_class.split(glyph_ids)
    assert tokens == [
        [84, 112, 93, 104, 82, 61, 96, 102, 93],
        [104, 87],
        [110],
    ]


def test_split_2() -> None:
    matchers = [[67, 112, 96], [74, 112, 76]]
    test_class: GlyphArraySplitter = GlyphArraySplitterRegexImpl(matchers)
    glyph_ids = [67, 112, 96, 103, 93, 108, 93]
    tokens = test_class.split(glyph_ids)
    assert tokens == [[67, 112, 96], [103, 93, 108, 93]]


def test_split_3() -> None:
    matchers = [[67, 112, 96], [74, 112, 76]]
    test_class: GlyphArraySplitter = GlyphArraySplitterRegexImpl(matchers)
    glyph_ids = [94, 67, 112, 96, 112, 91, 103]
    tokens = test_class.split(glyph_ids)
    assert tokens == [[94], [67, 112, 96], [112, 91, 103]]


def test_split_4() -> None:
    matchers = [[67, 112], [76, 112]]
    test_class: GlyphArraySplitter = GlyphArraySplitterRegexImpl(matchers)
    glyph_ids = [94, 167, 112, 91, 103]
    tokens = test_class.split(glyph_ids)
    assert tokens == [[94, 167, 112, 91, 103]]
