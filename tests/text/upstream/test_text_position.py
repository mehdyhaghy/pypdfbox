"""Upstream-style parity tests for ``TextPosition``.

Apache PDFBox 3.0.x does not ship a standalone ``TextPositionTest``;
``TextPosition`` is exercised through ``TestTextStripper`` and the
``PDFTextStripper`` integration suites. The cases below mirror the
invariants that upstream relies on inside those suites — the assertions
that would fail if the class diverged from documented behavior.
"""

from __future__ import annotations

import unicodedata

from pypdfbox.text.text_position import TextPosition


def _tp(text: str = "x", **overrides) -> TextPosition:
    base: dict = {
        "text": text,
        "x": 0.0,
        "y": 0.0,
        "font_size": 12.0,
        "width": 6.0,
    }
    base.update(overrides)
    return TextPosition(**base)


# Invariant: getCharacter and getUnicode return the same string.
def test_get_character_matches_get_unicode():
    tp = _tp("Hello")
    assert tp.get_character() == tp.get_unicode()


# Invariant: contains() is reflexive on overlapping baselines.
def test_contains_is_reflexive():
    tp = _tp(width=10.0)
    assert tp.contains(tp)


# Invariant: end_x = x + width.
def test_get_end_x_equals_x_plus_width():
    tp = _tp(x=5.0, width=15.0)
    assert tp.get_end_x() == 20.0


# Invariant: getDir defaults to 0 and reflects field updates.
def test_get_dir_zero_default():
    assert _tp().get_dir() == 0.0


def test_get_dir_reflects_field():
    assert _tp(dir=180.0).get_dir() == 180.0


# Invariant: a pure combining mark is a diacritic.
def test_is_diacritic_for_combining_acute():
    decomposed = unicodedata.normalize("NFD", "é")
    assert _tp(text=decomposed[1:]).is_diacritic()


# Invariant: merge_diacritic appends and extends width.
def test_merge_diacritic_extends_width():
    decomposed = unicodedata.normalize("NFD", "é")
    base = _tp("e", width=8.0)
    base.merge_diacritic(_tp(decomposed[1:], width=2.0))
    assert base.width == 10.0
    assert base.text.endswith(decomposed[1:])


# Invariant: getIndividualWidths length matches text length.
def test_individual_widths_length_matches_text():
    tp = _tp("abcd", width=20.0)
    assert len(tp.get_individual_widths()) == 4


# Invariant: getXScale / getYScale read text matrix when present.
def test_x_scale_reads_matrix():
    tp = _tp(text_matrix=[5.0, 0.0, 0.0, 7.0, 0.0, 0.0])
    assert tp.get_x_scale() == 5.0
    assert tp.get_y_scale() == 7.0


# Invariant: getFontSizeInPt falls back to getFontSize when no scaled
# size is recorded.
def test_font_size_in_pt_default_falls_back():
    tp = _tp(font_size=14.0)
    assert tp.get_font_size_in_pt() == tp.get_font_size()


# Invariant: getRotation defaults to 0 and is preserved.
def test_rotation_round_trips():
    assert _tp(rotation=270.0).get_rotation() == 270.0
