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


# Invariant (upstream TextPosition.java line 840): toString returns
# the decoded characters.
def test_to_string_returns_decoded_text():
    assert _tp(text="hello").to_string() == "hello"


# Invariant (upstream TextPosition.java line 972): hashCode is stable
# while the equals-comparable subset is unchanged.
def test_hash_code_stable_across_text_mutation():
    tp = _tp(text="a", x=10.0, y=20.0)
    h_before = tp.hash_code()
    tp.text = "z"
    assert tp.hash_code() == h_before


# Invariant (upstream getXRot, line 293): 0/90/180/270 cases.
def test_get_x_rot_axes():
    tp = _tp(x=10.0, y=20.0, page_width=500.0, page_height=800.0)
    assert tp._get_x_rot(0.0) == 10.0
    assert tp._get_x_rot(90.0) == 20.0
    assert tp._get_x_rot(180.0) == 490.0
    assert tp._get_x_rot(270.0) == 780.0


# Invariant (upstream getYLowerLeftRot, line 356): 0/90/180/270 cases.
def test_get_y_lower_left_rot_axes():
    tp = _tp(x=10.0, y=20.0, page_width=500.0, page_height=800.0)
    assert tp._get_y_lower_left_rot(0.0) == 20.0
    assert tp._get_y_lower_left_rot(90.0) == 490.0
    assert tp._get_y_lower_left_rot(180.0) == 780.0
    assert tp._get_y_lower_left_rot(270.0) == 10.0


# Invariant (upstream combineDiacritic, line 793): non-combining
# diacritic → combining counterpart via the static map.
def test_combine_diacritic_apostrophe_maps_to_acute():
    # 0x0027 (APOSTROPHE) → U+0301 (combining acute).
    assert TextPosition._combine_diacritic("'") == "́"


# Invariant (upstream combineDiacritic, line 793): characters not in
# the static map go through NFKC normalisation + trim.
def test_combine_diacritic_nfkc_fallback():
    # Diaeresis (U+00A8) NFKC-decomposes to "<space><U+0308>"; the
    # trim() upstream applies leaves the combining diaeresis only.
    assert TextPosition._combine_diacritic("¨") == "̈"


# Invariant (upstream insertDiacritic, line 753): inserts the combined
# diacritic immediately after the base character at the given index.
def test_insert_diacritic_appends_to_base_glyph():
    base = _tp(text="e", width=8.0)
    base._insert_diacritic(0, _tp(text="'"))  # apostrophe maps to combining acute
    # Result is the decomposed form: base char followed by U+0301.
    assert base.text == "e\u0301"
    # NFC-composing yields the precomposed character U+00E9.
    assert unicodedata.normalize("NFC", base.text) == "\u00e9"
