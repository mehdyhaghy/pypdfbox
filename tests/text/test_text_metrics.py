from __future__ import annotations

import pytest

from pypdfbox.text import TextMetrics, TextPosition


def _make_position(
    text: str = "A",
    x: float = 10.0,
    y: float = 20.0,
    font_size: float = 12.0,
) -> TextPosition:
    return TextPosition(text=text, x=x, y=y, font_size=font_size)


def test_construction_seeds_x_y_from_text_position() -> None:
    tp = _make_position(x=42.5, y=88.25)
    metrics = TextMetrics(tp)
    assert metrics.get_x() == 42.5
    assert metrics.get_y() == 88.25


def test_construction_derives_ascent_descent_from_font_size() -> None:
    tp = _make_position(font_size=10.0)
    metrics = TextMetrics(tp)
    assert metrics.get_ascent() == pytest.approx(7.0)
    assert metrics.get_descent() == pytest.approx(-2.0)


def test_get_height_is_ascent_plus_abs_descent() -> None:
    tp = _make_position(font_size=10.0)
    metrics = TextMetrics(tp)
    # 7.0 (ascent) + |-2.0| (descent) == 9.0
    assert metrics.get_height() == pytest.approx(9.0)


def test_get_height_with_zero_font_size_is_zero() -> None:
    tp = _make_position(font_size=0.0)
    metrics = TextMetrics(tp)
    assert metrics.get_ascent() == 0.0
    assert metrics.get_descent() == 0.0
    assert metrics.get_height() == 0.0


def test_set_ascent_updates_value_and_height() -> None:
    tp = _make_position(font_size=10.0)
    metrics = TextMetrics(tp)
    metrics.set_ascent(15.0)
    assert metrics.get_ascent() == 15.0
    # height now = 15 + |-2| = 17
    assert metrics.get_height() == pytest.approx(17.0)


def test_set_descent_updates_value_and_height() -> None:
    tp = _make_position(font_size=10.0)
    metrics = TextMetrics(tp)
    metrics.set_descent(-5.0)
    assert metrics.get_descent() == -5.0
    # height now = 7 + |-5| = 12
    assert metrics.get_height() == pytest.approx(12.0)


def test_set_descent_with_positive_value_still_contributes_magnitude() -> None:
    tp = _make_position(font_size=10.0)
    metrics = TextMetrics(tp)
    metrics.set_descent(3.0)
    assert metrics.get_descent() == 3.0
    # height = 7 + |3| = 10
    assert metrics.get_height() == pytest.approx(10.0)


def test_x_y_are_independent_floats() -> None:
    tp = _make_position(x=1.0, y=2.0, font_size=10.0)
    metrics = TextMetrics(tp)
    # Mutating the source TextPosition does not retroactively update the
    # snapshot held by TextMetrics.
    tp.x = 99.0
    tp.y = 99.0
    assert metrics.get_x() == 1.0
    assert metrics.get_y() == 2.0


def test_setters_coerce_to_float() -> None:
    tp = _make_position(font_size=10.0)
    metrics = TextMetrics(tp)
    metrics.set_ascent(8)
    metrics.set_descent(-3)
    assert isinstance(metrics.get_ascent(), float)
    assert isinstance(metrics.get_descent(), float)
    assert metrics.get_ascent() == 8.0
    assert metrics.get_descent() == -3.0
