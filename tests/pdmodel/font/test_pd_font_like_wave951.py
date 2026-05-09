from __future__ import annotations

from pypdfbox.pdmodel.font import PDFontLike
from tests.pdmodel.font.test_pd_font_like_wave924 import _WrongSigFontLike


def test_wave951_wrong_signature_stub_methods_are_executable() -> None:
    font = _WrongSigFontLike()

    assert isinstance(font, PDFontLike)
    assert font.get_font_descriptor() == 0
    assert font.get_font_matrix() is None
    assert font.get_bounding_box() is None
    assert font.get_position_vector(65) is None
    assert font.get_height(65) == ""
    assert font.get_width(65) == ""
    assert font.has_explicit_width(65) == ""
    assert font.get_width_from_font(65) == ""
    assert font.is_embedded() == ""
    assert font.is_damaged() == ""
    assert font.get_average_font_width() == ""
