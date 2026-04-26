from __future__ import annotations

from pypdfbox.fontbox.ttf import wgl4_names


def test_all_names() -> None:
    """``testAllNames`` upstream port."""
    all_names = wgl4_names.get_all_names()
    assert all_names is not None
    assert len(all_names) == wgl4_names.NUMBER_OF_MAC_GLYPHS


def test_get_glyph_name() -> None:
    """``testGetGlyphName`` upstream port."""
    assert wgl4_names.get_glyph_name(0) == ".notdef"
    assert wgl4_names.get_glyph_name(32) == "equal"
    assert wgl4_names.get_glyph_name(75) == "h"
    assert wgl4_names.get_glyph_name(201) == "Aacute"
    assert wgl4_names.get_glyph_name(209) == "Ocircumflex"
    assert wgl4_names.get_glyph_name(256) == "ccaron"
    assert wgl4_names.get_glyph_name(wgl4_names.NUMBER_OF_MAC_GLYPHS + 1) is None
    assert wgl4_names.get_glyph_name(-1) is None


def test_glyph_indices() -> None:
    """``testGlyphIndices`` upstream port."""
    assert wgl4_names.get_glyph_index(".notdef") == 0
    assert wgl4_names.get_glyph_index("equal") == 32
    assert wgl4_names.get_glyph_index("h") == 75
    assert wgl4_names.get_glyph_index("Aacute") == 201
    assert wgl4_names.get_glyph_index("Ocircumflex") == 209
    assert wgl4_names.get_glyph_index("ccaron") == 256
    assert wgl4_names.get_glyph_index("INVALID") is None
