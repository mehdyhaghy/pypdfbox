from __future__ import annotations

import math
from typing import Any

from pypdfbox.text.text_position import TextPosition


def _make(**overrides: Any) -> TextPosition:
    base: dict[str, Any] = {
        "text": "x",
        "x": 0.0,
        "y": 0.0,
        "font_size": 12.0,
        "width": 6.0,
    }
    base.update(overrides)
    return TextPosition(**base)


def test_matrix_scale_uses_vector_magnitude_for_rotated_text_wave307() -> None:
    pos = _make(text_matrix=[0.0, 2.0, -3.0, 0.0, 100.0, 200.0])

    assert pos.get_x_scale() == 2.0
    assert pos.get_y_scale() == 3.0


def test_matrix_scale_handles_sheared_basis_vectors_wave307() -> None:
    pos = _make(text_matrix=[3.0, 4.0, 5.0, 12.0, 0.0, 0.0])

    assert pos.get_x_scale() == 5.0
    assert pos.get_y_scale() == 13.0


def test_matrix_scale_short_matrix_still_defaults_wave307() -> None:
    pos = _make(text_matrix=[math.nan])

    assert pos.get_x_scale() == 1.0
    assert pos.get_y_scale() == 1.0
