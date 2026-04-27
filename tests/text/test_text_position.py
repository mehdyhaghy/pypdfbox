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
