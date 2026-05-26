from __future__ import annotations

from pypdfbox.fontbox.encoding import GlyphList


def test_u_unicode_lookup_rejects_five_and_six_digit_code_points() -> None:
    # Upstream ``GlyphList.toUnicode`` only synthesizes a ``u`` name when its
    # length is exactly 5 (one 4-hex code point). Longer ``u`` forms
    # (``uXXXXX`` / ``uXXXXXX``) are NOT synthesized — they resolve to null.
    # Verified against the live PDFBox 3.0.7 oracle (wave 1417):
    #   u1F600 -> NULL, u01F600 -> NULL.
    glyph_list = GlyphList.get_default()

    assert glyph_list.to_unicode("u1F600") is None
    assert glyph_list.to_unicode("u01F600") is None
    assert glyph_list.get_or_unicode_lookup("u1F600") is None
    assert glyph_list.code_point_for_glyph_name("u1F600") is None
    # The 5-char ``u`` form IS synthesized (one 4-hex code point).
    assert glyph_list.to_unicode("u0041") == "A"


def test_u_unicode_lookup_rejects_code_points_outside_unicode_range() -> None:
    glyph_list = GlyphList.get_default()

    # ``u110000`` is length 7, not 5 — not a recognized ``u`` synthesis name.
    assert GlyphList.is_unicode_lookup("u110000") is False
    assert glyph_list.to_unicode("u110000") is None
    assert glyph_list.get_or_unicode_lookup("uFFFFFF") is None
    assert glyph_list.code_point_for_glyph_name("u110000") is None
