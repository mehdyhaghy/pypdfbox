from __future__ import annotations

from tests.text.test_pdf_text_stripper_wave488 import StallingCMap, WidthFont


def test_wave962_stalling_cmap_unicode_helper_returns_marker() -> None:
    assert StallingCMap().to_unicode(65) == "unreachable"


def test_wave962_width_font_returns_zero_for_non_space_code() -> None:
    assert WidthFont().get_glyph_width(65) == 0.0
