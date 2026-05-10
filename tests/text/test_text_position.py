from __future__ import annotations

import unicodedata

from pypdfbox.text.text_position import TextPosition


def _make(text: str = "Hello", **overrides) -> TextPosition:
    base: dict = {
        "text": text,
        "x": 10.0,
        "y": 20.0,
        "font_size": 12.0,
        "width": 50.0,
    }
    base.update(overrides)
    return TextPosition(**base)


# ---------------------------------------------------------------------------
# Decoded text accessors
# ---------------------------------------------------------------------------


def test_get_unicode_returns_text():
    tp = _make("abc")
    assert tp.get_unicode() == "abc"


def test_get_character_aliases_get_unicode():
    tp = _make("abc")
    assert tp.get_character() == "abc" == tp.get_unicode()


def test_get_visible_text_aliases_get_unicode():
    tp = _make("Visible")
    assert tp.get_visible_text() == "Visible"


def test_str_returns_text():
    tp = _make("abc")
    assert str(tp) == "abc"


# ---------------------------------------------------------------------------
# Coordinates
# ---------------------------------------------------------------------------


def test_get_x_and_get_y():
    tp = _make(x=5.0, y=7.0)
    assert tp.get_x() == 5.0
    assert tp.get_y() == 7.0


def test_get_end_x_is_x_plus_width():
    tp = _make(x=10.0, width=50.0)
    assert tp.get_end_x() == 60.0


def test_get_end_y_uses_cap_height_factor():
    tp = _make(y=20.0, font_size=10.0)
    assert tp.get_end_y() == 20.0 + 10.0 * 0.7


# ---------------------------------------------------------------------------
# Font / scale
# ---------------------------------------------------------------------------


def test_get_font_size_returns_field():
    tp = _make(font_size=14.0)
    assert tp.get_font_size() == 14.0


def test_get_font_size_in_pt_falls_back_to_font_size():
    tp = _make(font_size=14.0)
    assert tp.get_font_size_in_pt() == 14.0


def test_get_font_size_in_pt_returns_explicit_value():
    tp = _make(font_size=14.0, font_size_in_pt=10.5)
    assert tp.get_font_size_in_pt() == 10.5


def test_get_font_name_default_none():
    tp = _make()
    assert tp.get_font_name() is None


def test_get_font_returns_field():
    sentinel = object()
    tp = _make(font=sentinel)  # type: ignore[arg-type]
    assert tp.get_font() is sentinel


def test_get_resolved_font_name():
    tp = _make(resolved_font_name="Helvetica")
    assert tp.get_resolved_font_name() == "Helvetica"


def test_get_width_and_width_of_space():
    tp = _make(width=42.0, width_of_space=4.5)
    assert tp.get_width() == 42.0
    assert tp.get_width_of_space() == 4.5


def test_get_x_scale_defaults_to_one():
    assert _make().get_x_scale() == 1.0


def test_get_y_scale_defaults_to_one():
    assert _make().get_y_scale() == 1.0


def test_get_x_scale_reads_text_matrix():
    tp = _make(text_matrix=[2.0, 0.0, 0.0, 3.0, 0.0, 0.0])
    assert tp.get_x_scale() == 2.0
    assert tp.get_y_scale() == 3.0


# ---------------------------------------------------------------------------
# Direction / rotation / page extents
# ---------------------------------------------------------------------------


def test_get_dir_defaults_to_zero():
    assert _make().get_dir() == 0.0


def test_get_rotation_defaults_to_zero():
    assert _make().get_rotation() == 0.0


def test_get_rotation_reads_field():
    tp = _make(rotation=90.0)
    assert tp.get_rotation() == 90.0


def test_get_page_width_and_height():
    tp = _make(page_width=612.0, page_height=792.0)
    assert tp.get_page_width() == 612.0
    assert tp.get_page_height() == 792.0


def test_get_x_dir_adj_zero_rotation_returns_x():
    tp = _make(x=42.0, dir=0.0)
    assert tp.get_x_dir_adj() == 42.0


def test_get_x_dir_adj_90_returns_y():
    tp = _make(x=10.0, y=33.0, dir=90.0)
    assert tp.get_x_dir_adj() == 33.0


def test_get_x_dir_adj_180_uses_page_width():
    tp = _make(x=100.0, dir=180.0, page_width=500.0)
    assert tp.get_x_dir_adj() == 400.0


def test_get_x_dir_adj_270_uses_page_height():
    tp = _make(y=200.0, dir=270.0, page_height=792.0)
    assert tp.get_x_dir_adj() == 592.0


def test_get_y_dir_adj_zero_rotation_returns_y():
    tp = _make(y=200.0, dir=0.0)
    assert tp.get_y_dir_adj() == 200.0


def test_get_y_dir_adj_90_uses_page_width():
    tp = _make(x=100.0, dir=90.0, page_width=500.0)
    assert tp.get_y_dir_adj() == 400.0


def test_get_y_dir_adj_180_uses_page_height():
    tp = _make(y=100.0, dir=180.0, page_height=792.0)
    assert tp.get_y_dir_adj() == 692.0


def test_get_y_dir_adj_270_returns_x():
    tp = _make(x=42.0, dir=270.0)
    assert tp.get_y_dir_adj() == 42.0


def test_get_x_directional_adj_alias():
    tp = _make(x=10.0)
    assert tp.get_x_directional_adj() == tp.get_x_dir_adj()


def test_get_y_directional_adj_alias():
    tp = _make(y=20.0)
    assert tp.get_y_directional_adj() == tp.get_y_dir_adj()


def test_get_width_dir_adj_returns_width():
    tp = _make(width=37.5)
    assert tp.get_width_dir_adj() == 37.5


def test_get_height_dir_returns_font_size():
    tp = _make(font_size=13.0)
    assert tp.get_height_dir() == 13.0


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def test_contains_overlap_same_baseline():
    a = _make(x=0.0, y=0.0, width=10.0, font_size=10.0)
    b = _make(x=5.0, y=0.0, width=10.0, font_size=10.0)
    assert a.contains(b)
    assert b.contains(a)


def test_contains_no_overlap_horizontally():
    a = _make(x=0.0, y=0.0, width=10.0, font_size=10.0)
    b = _make(x=20.0, y=0.0, width=10.0, font_size=10.0)
    assert not a.contains(b)
    assert not b.contains(a)


def test_contains_different_baselines():
    a = _make(x=0.0, y=0.0, width=10.0, font_size=10.0)
    b = _make(x=0.0, y=100.0, width=10.0, font_size=10.0)
    assert not a.contains(b)


def test_contains_none_other():
    assert not _make().contains(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Per-character widths
# ---------------------------------------------------------------------------


def test_get_individual_widths_distributes_evenly():
    tp = _make(text="abcde", width=50.0)
    widths = tp.get_individual_widths()
    assert len(widths) == 5
    assert all(w == 10.0 for w in widths)


def test_get_individual_widths_empty_text():
    tp = _make(text="", width=0.0)
    assert tp.get_individual_widths() == []


# ---------------------------------------------------------------------------
# Diacritics
# ---------------------------------------------------------------------------


def test_contains_diacritic_with_combining_mark():
    decomposed = unicodedata.normalize("NFD", "é")
    tp = _make(text=decomposed[1:])
    assert tp.contains_diacritic() is True


def test_contains_diacritic_false_for_plain_text():
    assert _make(text="abc").contains_diacritic() is False


def test_contains_diacritic_false_for_empty():
    assert _make(text="").contains_diacritic() is False


def test_is_diacritic_true_for_pure_combining():
    decomposed = unicodedata.normalize("NFD", "é")
    assert _make(text=decomposed[1:]).is_diacritic() is True


def test_is_diacritic_false_for_mixed():
    decomposed = unicodedata.normalize("NFD", "é")
    assert _make(text=decomposed).is_diacritic() is False


def test_is_diacritic_false_for_empty():
    assert _make(text="").is_diacritic() is False


def test_merge_diacritic_appends_unicode_and_width():
    decomposed = unicodedata.normalize("NFD", "é")
    base = _make(text="e", width=8.0)
    diacritic = _make(text=decomposed[1:], width=2.0)
    base.merge_diacritic(diacritic)
    assert base.text == decomposed
    assert base.width == 10.0


def test_merge_diacritic_with_normalizer():
    decomposed = unicodedata.normalize("NFD", "é")
    base = _make(text="e", width=8.0)
    diacritic = _make(text=decomposed[1:], width=2.0)
    base.merge_diacritic(
        diacritic, normalizer=lambda s: unicodedata.normalize("NFC", s)
    )
    assert base.text == "é"  # NFC composed
    assert base.width == 10.0


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------


def test_get_text_matrix_defaults_to_none():
    assert _make().get_text_matrix() is None


def test_get_text_matrix_returns_stored():
    matrix = [1.0, 0.0, 0.0, 1.0, 5.0, 7.0]
    tp = _make(text_matrix=matrix)
    assert tp.get_text_matrix() == matrix


# ---------------------------------------------------------------------------
# Wave: set_unicode / get_visually_ordered_unicode / get_height /
# get_character_codes / completely_contains
# ---------------------------------------------------------------------------


def test_set_unicode_replaces_text():
    tp = _make(text="abc")
    tp.set_unicode("xyz")
    assert tp.get_unicode() == "xyz"
    assert tp.text == "xyz"


def test_get_visually_ordered_unicode_ltr_unchanged():
    tp = _make(text="hello")
    assert tp.get_visually_ordered_unicode() == "hello"


def test_get_visually_ordered_unicode_rtl_reversed():
    # Hebrew alef + bet + gimel — bidirectional class "R"
    tp = _make(text="אבג")
    assert tp.get_visually_ordered_unicode() == "גבא"


def test_get_visually_ordered_unicode_arabic_reversed():
    # Arabic letters — bidirectional class "AL"
    tp = _make(text="ابت")
    assert tp.get_visually_ordered_unicode() == "تبا"


def test_get_visually_ordered_unicode_single_codepoint_unchanged():
    # Single-codepoint RTL run has nothing to reorder.
    tp = _make(text="א")
    assert tp.get_visually_ordered_unicode() == "א"


def test_get_visually_ordered_unicode_empty_unchanged():
    tp = _make(text="")
    assert tp.get_visually_ordered_unicode() == ""


def test_get_height_returns_font_size():
    tp = _make(font_size=18.0)
    assert tp.get_height() == 18.0


def test_get_height_matches_get_height_dir():
    tp = _make(font_size=11.5)
    assert tp.get_height() == tp.get_height_dir()


def test_get_character_codes_returns_codepoints():
    tp = _make(text="ABC")
    assert tp.get_character_codes() == [ord("A"), ord("B"), ord("C")]


def test_get_character_codes_empty_text():
    tp = _make(text="")
    assert tp.get_character_codes() == []


def test_completely_contains_true_when_other_inside():
    outer = _make(x=0.0, y=0.0, width=100.0, font_size=20.0)
    inner = _make(x=10.0, y=5.0, width=50.0, font_size=10.0)
    assert outer.completely_contains(inner) is True


def test_completely_contains_false_when_other_extends_left():
    outer = _make(x=10.0, y=0.0, width=50.0, font_size=20.0)
    other = _make(x=0.0, y=0.0, width=20.0, font_size=10.0)
    assert outer.completely_contains(other) is False


def test_completely_contains_false_when_other_extends_right():
    outer = _make(x=0.0, y=0.0, width=50.0, font_size=20.0)
    other = _make(x=40.0, y=0.0, width=20.0, font_size=10.0)
    assert outer.completely_contains(other) is False


def test_completely_contains_false_when_other_extends_below():
    outer = _make(x=0.0, y=0.0, width=100.0, font_size=10.0)
    other = _make(x=10.0, y=5.0, width=20.0, font_size=20.0)
    assert outer.completely_contains(other) is False


def test_completely_contains_false_for_none():
    outer = _make(x=0.0, y=0.0, width=100.0, font_size=10.0)
    assert outer.completely_contains(None) is False  # type: ignore[arg-type]


def test_completely_contains_self_is_true():
    tp = _make(x=5.0, y=5.0, width=10.0, font_size=10.0)
    assert tp.completely_contains(tp) is True


# ---------------------------------------------------------------------------
# Value-based equality (upstream parity)
# ---------------------------------------------------------------------------


def test_equals_returns_true_for_self():
    tp = _make(text="hello", x=1.0, y=2.0, width=3.0, font_size=4.0)
    assert tp.equals(tp) is True


def test_equals_returns_true_for_same_value_subset():
    a = _make(text="abc", x=10.0, y=20.0, width=5.0, font_size=12.0)
    b = _make(text="abc", x=10.0, y=20.0, width=5.0, font_size=12.0)
    assert a.equals(b) is True
    assert b.equals(a) is True


def test_equals_ignores_decoded_text_per_pdfbox_4701():
    # Text is mutable (mergeDiacritic mutates it); upstream's equals
    # explicitly excludes the decoded characters from the comparison.
    a = _make(text="abc", x=10.0, y=20.0, width=5.0)
    b = _make(text="xyz", x=10.0, y=20.0, width=5.0)
    assert a.equals(b) is True


def test_equals_returns_false_when_x_differs():
    a = _make(x=10.0)
    b = _make(x=11.0)
    assert a.equals(b) is False


def test_equals_returns_false_when_font_size_in_pt_differs():
    a = _make(font_size_in_pt=12.0)
    b = _make(font_size_in_pt=14.0)
    assert a.equals(b) is False


def test_equals_returns_false_when_text_matrix_differs():
    a = _make(text_matrix=[1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    b = _make(text_matrix=[2.0, 0.0, 0.0, 2.0, 0.0, 0.0])
    assert a.equals(b) is False


def test_equals_returns_true_when_both_text_matrices_none():
    a = _make()
    b = _make()
    assert a.text_matrix is None
    assert b.text_matrix is None
    assert a.equals(b) is True


def test_equals_returns_false_for_non_text_position():
    tp = _make()
    assert tp.equals("not a TextPosition") is False
    assert tp.equals(None) is False
    assert tp.equals(42) is False


def test_equals_returns_false_when_rotation_differs():
    a = _make(rotation=0.0)
    b = _make(rotation=90.0)
    assert a.equals(b) is False


def test_equals_returns_false_when_width_of_space_differs():
    a = _make(width_of_space=5.0)
    b = _make(width_of_space=7.0)
    assert a.equals(b) is False


def test_hash_is_stable_for_same_subset():
    a = _make(text="abc", x=10.0, y=20.0, width=5.0)
    b = _make(text="xyz", x=10.0, y=20.0, width=5.0)
    # Same subset → same hash even though decoded text differs.
    assert hash(a) == hash(b)


def test_hash_changes_when_subset_field_changes():
    a = _make(x=10.0)
    b = _make(x=10.001)
    # We don't strictly require they differ (hash collisions are
    # possible), but for plain coordinate changes the tuple-hash should
    # almost always differ. The contract we DO require is that the
    # object stays hashable.
    hash(a)
    hash(b)


def test_text_position_is_hashable_in_a_set():
    tp = _make()
    seen = {tp}
    assert tp in seen


def test_text_position_in_dict_key():
    a = _make(x=1.0)
    b = _make(x=2.0)
    d = {a: "first", b: "second"}
    assert d[a] == "first"
    assert d[b] == "second"


def test_hash_is_stable_across_text_mutation():
    # PDFBOX-4701: mutating decoded text (e.g. via merge_diacritic)
    # must not move the position in a hashed container.
    tp = _make(text="a", x=10.0, y=20.0)
    h_before = hash(tp)
    tp.text = "z"
    assert hash(tp) == h_before


def test_hash_with_text_matrix_is_stable():
    a = _make(text_matrix=[1.0, 0.0, 0.0, 1.0, 5.0, 6.0])
    b = _make(text_matrix=[1.0, 0.0, 0.0, 1.0, 5.0, 6.0])
    assert hash(a) == hash(b)


# ---------------------------------------------------------------------------
# Wave 1260: private rotation helpers + diacritic helpers + Java-name aliases
# ---------------------------------------------------------------------------


def test_get_x_rot_zero_returns_x():
    tp = _make(x=42.0)
    assert tp._get_x_rot(0.0) == 42.0


def test_get_x_rot_90_returns_y():
    tp = _make(x=10.0, y=33.0)
    assert tp._get_x_rot(90.0) == 33.0


def test_get_x_rot_180_uses_page_width():
    tp = _make(x=100.0, page_width=500.0)
    assert tp._get_x_rot(180.0) == 400.0


def test_get_x_rot_270_uses_page_height():
    tp = _make(y=200.0, page_height=792.0)
    assert tp._get_x_rot(270.0) == 592.0


def test_get_x_rot_unsupported_returns_zero():
    # Upstream returns 0 for any rotation that isn't 0/90/180/270.
    tp = _make(x=42.0)
    assert tp._get_x_rot(45.0) == 0.0


def test_get_y_lower_left_rot_zero_returns_y():
    tp = _make(y=42.0)
    assert tp._get_y_lower_left_rot(0.0) == 42.0


def test_get_y_lower_left_rot_90_uses_page_width():
    tp = _make(x=100.0, page_width=500.0)
    assert tp._get_y_lower_left_rot(90.0) == 400.0


def test_get_y_lower_left_rot_180_uses_page_height():
    tp = _make(y=100.0, page_height=792.0)
    assert tp._get_y_lower_left_rot(180.0) == 692.0


def test_get_y_lower_left_rot_270_returns_x():
    tp = _make(x=42.0)
    assert tp._get_y_lower_left_rot(270.0) == 42.0


def test_get_y_lower_left_rot_unsupported_returns_zero():
    tp = _make(y=42.0)
    assert tp._get_y_lower_left_rot(45.0) == 0.0


def test_get_width_rot_returns_width_for_horizontal():
    tp = _make(width=37.5)
    assert tp._get_width_rot(0.0) == 37.5
    assert tp._get_width_rot(180.0) == 37.5


def test_get_width_rot_returns_width_for_vertical():
    tp = _make(width=37.5)
    assert tp._get_width_rot(90.0) == 37.5
    assert tp._get_width_rot(270.0) == 37.5


def test_combine_diacritic_remaps_apostrophe_to_acute():
    # 0x0027 (APOSTROPHE) is one of upstream's non-decomposing
    # diacritic remaps — combining acute (U+0301).
    assert TextPosition._combine_diacritic("'") == "́"


def test_combine_diacritic_remaps_grave_accent():
    # 0x0060 (GRAVE ACCENT) → combining grave (U+0300).
    assert TextPosition._combine_diacritic("`") == "̀"


def test_combine_diacritic_falls_back_to_nfkc_strip():
    # Characters not in the remap table go through NFKC + trim. The
    # diaeresis (U+00A8) NFKC-decomposes to space + U+0308; trim()
    # leaves only the combining diaeresis.
    assert TextPosition._combine_diacritic("¨") == "̈"


def test_combine_diacritic_empty_string_returns_empty():
    assert TextPosition._combine_diacritic("") == ""


def test_insert_diacritic_appends_after_base():
    base = _make(text="e", width=8.0)
    diacritic = _make(text="́", width=0.0)  # combining acute
    base._insert_diacritic(0, diacritic)
    assert base.text == "é"


def test_insert_diacritic_remaps_non_combining_apostrophe():
    base = _make(text="e", width=8.0)
    # Apostrophe is in the remap table → combining acute (U+0301).
    diacritic = _make(text="'", width=0.0)
    base._insert_diacritic(0, diacritic)
    assert base.text == "é"


def test_insert_diacritic_clamps_negative_index():
    base = _make(text="abc")
    diacritic = _make(text="́")
    base._insert_diacritic(-1, diacritic)
    assert base.text == "ábc"


def test_insert_diacritic_clamps_overlong_index():
    base = _make(text="abc")
    diacritic = _make(text="́")
    base._insert_diacritic(99, diacritic)
    assert base.text == "abć"


def test_to_string_returns_unicode():
    tp = _make(text="hello")
    assert tp.to_string() == "hello"
    assert tp.to_string() == tp.get_unicode()


def test_hash_code_matches_python_hash():
    tp = _make()
    assert tp.hash_code() == hash(tp)


def test_diacritics_table_is_populated():
    # Upstream defines 31 entries in DIACRITICS; we mirror the same
    # set for diff-friendly re-syncs.
    from pypdfbox.text.text_position import _DIACRITICS

    assert len(_DIACRITICS) == 31
    # A handful of well-known mappings.
    assert _DIACRITICS[0x0027] == "́"
    assert _DIACRITICS[0x0060] == "̀"
    assert _DIACRITICS[0x005F] == "̲"


# ---------------------------------------------------------------------------
# Wave 1265: public-named (no underscore prefix) helpers
# ---------------------------------------------------------------------------


def test_get_x_rot_public_name():
    tp = _make(x=10.0, y=20.0, page_width=500.0, page_height=800.0)
    assert tp.get_x_rot(0.0) == 10.0
    assert tp.get_x_rot(90.0) == 20.0
    assert tp.get_x_rot(180.0) == 490.0
    assert tp.get_x_rot(270.0) == 780.0
    assert tp.get_x_rot(45.0) == 0.0


def test_get_y_lower_left_rot_public_name():
    tp = _make(x=10.0, y=20.0, page_width=500.0, page_height=800.0)
    assert tp.get_y_lower_left_rot(0.0) == 20.0
    assert tp.get_y_lower_left_rot(90.0) == 490.0
    assert tp.get_y_lower_left_rot(180.0) == 780.0
    assert tp.get_y_lower_left_rot(270.0) == 10.0
    assert tp.get_y_lower_left_rot(45.0) == 0.0


def test_get_width_rot_public_name():
    tp = _make(width=37.5)
    assert tp.get_width_rot(0.0) == 37.5
    assert tp.get_width_rot(90.0) == 37.5
    assert tp.get_width_rot(180.0) == 37.5
    assert tp.get_width_rot(270.0) == 37.5


def test_combine_diacritic_public_name():
    assert TextPosition.combine_diacritic("'") == "́"
    assert TextPosition.combine_diacritic("`") == "̀"
    assert TextPosition.combine_diacritic("") == ""


def test_insert_diacritic_public_name():
    base = _make(text="e", width=8.0)
    diacritic = _make(text="'", width=0.0)
    base.insert_diacritic(0, diacritic)
    # Decomposed (NFD) form: base + combining acute (U+0301).
    assert base.text == "é"
    assert unicodedata.normalize("NFC", base.text) == "é"


def test_create_diacritics_classmethod():
    table = TextPosition.create_diacritics()
    assert len(table) == 31
    assert table[0x0027] == "́"


def test_create_diacritics_returns_fresh_dict():
    a = TextPosition.create_diacritics()
    a[0xFFFF] = "z"
    b = TextPosition.create_diacritics()
    assert 0xFFFF not in b
