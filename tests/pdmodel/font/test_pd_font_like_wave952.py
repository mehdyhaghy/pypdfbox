from __future__ import annotations

from pypdfbox.pdmodel.font import PDFontLike
from tests.pdmodel.font.test_pd_font_like_wave924 import _ExtendedFontLike


def test_wave952_extended_stub_methods_are_executable() -> None:
    font = _ExtendedFontLike()

    assert isinstance(font, PDFontLike)
    assert font.get_name() == "Extended"
    assert font.get_font_descriptor() is None
    assert font.get_font_matrix() == []
    assert font.get_bounding_box() == ()
    assert font.get_position_vector(65) == (65, 0)
    assert font.get_height(65) == 65.0
    assert font.get_width(65) == 65.0
    assert font.has_explicit_width(65) is True
    assert font.has_explicit_width(66) is False
    assert font.get_width_from_font(65) == 65.0
    assert font.is_embedded() is False
    assert font.is_damaged() is False
    assert font.get_average_font_width() == 0.0
    assert font.extra() == "extra"
