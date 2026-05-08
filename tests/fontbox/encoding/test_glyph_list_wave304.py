from __future__ import annotations

from pypdfbox.fontbox.encoding import GlyphList


def test_reverse_lookup_prefers_standard_encoding_name_for_duplicates() -> None:
    glyph_list = GlyphList.get_default()

    assert glyph_list.to_unicode("ilde") == "\u02dc"
    assert glyph_list.to_unicode("tilde") == "\u02dc"
    assert glyph_list.code_point_to_name(0x02DC) == "tilde"
    assert glyph_list.code_point_to_name_or_notdef(0x02DC) == "tilde"


def test_sequence_lookup_prefers_standard_encoding_name_for_duplicates() -> None:
    assert GlyphList.get_default().sequence_to_name("\u02dc") == "tilde"
