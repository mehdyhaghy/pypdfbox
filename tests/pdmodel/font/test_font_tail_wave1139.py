from __future__ import annotations

from tests.pdmodel.font.test_font_tail_wave797 import _EmptyCharsetCFF


def test_empty_charset_cff_has_glyph_helper_accepts_only_a() -> None:
    font = _EmptyCharsetCFF()

    assert font.has_glyph("A") is True
    assert font.has_glyph("B") is False
