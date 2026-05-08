from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font import Type1Font


class _FakeT1:
    def __init__(self, font: dict[str, Any]) -> None:
        self.font = font


def _font_with_matrix(matrix: Any) -> Type1Font:
    font = Type1Font()
    font._t1 = _FakeT1({"FontName": "Wave294", "FontMatrix": matrix})
    return font


def test_get_font_matrix_uses_default_without_program() -> None:
    font = Type1Font()

    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert font.units_per_em == 1000


def test_get_font_matrix_uses_default_for_malformed_values() -> None:
    font = _font_with_matrix([0.001, 0, "bad", 0.001, 0, 0])

    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert font.units_per_em == 1000


def test_get_font_matrix_uses_default_for_short_matrix() -> None:
    font = _font_with_matrix([0.001, 0, 0])

    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
