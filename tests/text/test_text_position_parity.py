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


# --- Defaults for each new accessor ------------------------------------


def test_get_x_directional_adj_defaults_to_x():
    tp = _make()
    assert tp.get_x_directional_adj() == tp.get_x() == 10.0


def test_get_y_directional_adj_defaults_to_y():
    tp = _make()
    assert tp.get_y_directional_adj() == tp.get_y() == 20.0


def test_get_x_scale_defaults_to_one():
    tp = _make()
    assert tp.get_x_scale() == 1.0


def test_get_y_scale_defaults_to_one():
    tp = _make()
    assert tp.get_y_scale() == 1.0


def test_get_x_scale_reads_text_matrix():
    tp = _make(text_matrix=[2.0, 0.0, 0.0, 3.0, 0.0, 0.0])
    assert tp.get_x_scale() == 2.0
    assert tp.get_y_scale() == 3.0


def test_get_height_dir_returns_font_size():
    tp = _make()
    assert tp.get_height_dir() == 12.0


def test_get_dir_defaults_to_zero():
    tp = _make()
    assert tp.get_dir() == 0.0


def test_get_dir_reads_field():
    tp = _make(dir=90.0)
    assert tp.get_dir() == 90.0


def test_get_individual_widths_distributes_evenly():
    tp = _make(text="abcde", width=50.0)
    widths = tp.get_individual_widths()
    assert len(widths) == 5
    assert all(w == 10.0 for w in widths)


def test_get_individual_widths_empty_text():
    tp = _make(text="", width=0.0)
    assert tp.get_individual_widths() == []


def test_get_visible_text_aliases_get_unicode():
    tp = _make(text="Visible")
    assert tp.get_visible_text() == "Visible" == tp.get_unicode()


def test_get_text_matrix_defaults_to_none():
    tp = _make()
    assert tp.get_text_matrix() is None


def test_get_text_matrix_returns_stored():
    matrix = [1.0, 0.0, 0.0, 1.0, 5.0, 7.0]
    tp = _make(text_matrix=matrix)
    assert tp.get_text_matrix() == matrix


# --- Diacritics --------------------------------------------------------


def test_contains_diacritic_with_combining_mark():
    # Decomposed "é" -> "e" + combining acute (U+0301).
    decomposed = unicodedata.normalize("NFD", "é")
    # The combining mark is the diacritic; testing a run that *starts*
    # with the combining mark.
    tp = _make(text=decomposed[1:])
    assert tp.contains_diacritic() is True


def test_contains_diacritic_false_for_plain_text():
    tp = _make(text="abc")
    assert tp.contains_diacritic() is False


def test_contains_diacritic_false_for_empty():
    tp = _make(text="")
    assert tp.contains_diacritic() is False


def test_is_diacritic_true_for_pure_combining():
    decomposed = unicodedata.normalize("NFD", "é")
    tp = _make(text=decomposed[1:])  # only the combining acute
    assert tp.is_diacritic() is True


def test_is_diacritic_false_for_mixed():
    decomposed = unicodedata.normalize("NFD", "é")
    tp = _make(text=decomposed)  # "e" + combining acute
    assert tp.is_diacritic() is False


def test_is_diacritic_false_for_empty():
    tp = _make(text="")
    assert tp.is_diacritic() is False


def test_merge_diacritic_appends_unicode_and_width():
    decomposed = unicodedata.normalize("NFD", "é")
    base = _make(text="e", width=8.0)
    diacritic = _make(text=decomposed[1:], width=2.0)
    base.merge_diacritic(diacritic)
    assert base.text == decomposed  # "e" + combining acute
    assert base.width == 10.0


# --- Extents -----------------------------------------------------------


def test_get_end_x_is_x_plus_width():
    tp = _make(x=10.0, width=50.0)
    assert tp.get_end_x() == 60.0


def test_get_end_y_uses_cap_height_factor():
    tp = _make(y=20.0, font_size=10.0)
    assert tp.get_end_y() == 20.0 + 10.0 * 0.7
