from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common import PDImmutableRectangle


def test_construct_zeroed_lower_left() -> None:
    rect = PDImmutableRectangle(100.0, 200.0)
    assert rect.get_lower_left_x() == 0.0
    assert rect.get_lower_left_y() == 0.0
    assert rect.get_upper_right_x() == 100.0
    assert rect.get_upper_right_y() == 200.0


def test_setters_all_raise() -> None:
    rect = PDImmutableRectangle(50.0, 50.0)
    with pytest.raises(TypeError):
        rect.set_lower_left_x(1.0)
    with pytest.raises(TypeError):
        rect.set_lower_left_y(1.0)
    with pytest.raises(TypeError):
        rect.set_upper_right_x(1.0)
    with pytest.raises(TypeError):
        rect.set_upper_right_y(1.0)


def test_width_and_height() -> None:
    rect = PDImmutableRectangle(120.0, 240.0)
    assert rect.get_width() == pytest.approx(120.0)
    assert rect.get_height() == pytest.approx(240.0)
