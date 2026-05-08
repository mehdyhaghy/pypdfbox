from __future__ import annotations

from pypdfbox.fontbox.encoding import GlyphList


def test_u_unicode_lookup_accepts_five_and_six_digit_code_points() -> None:
    glyph_list = GlyphList.get_default()

    assert glyph_list.to_unicode("u1F600") == "\U0001f600"
    assert glyph_list.to_unicode("u01F600") == "\U0001f600"
    assert glyph_list.get_or_unicode_lookup("u1F600") == "\U0001f600"
    assert glyph_list.code_point_for_glyph_name("u1F600") == 0x1F600


def test_u_unicode_lookup_rejects_code_points_outside_unicode_range() -> None:
    glyph_list = GlyphList.get_default()

    assert GlyphList.is_unicode_lookup("u110000") is True
    assert glyph_list.to_unicode("u110000") is None
    assert glyph_list.get_or_unicode_lookup("uFFFFFF") is None
    assert glyph_list.code_point_for_glyph_name("u110000") is None
