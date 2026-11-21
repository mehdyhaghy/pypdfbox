"""Port of upstream ``GlyphListTest`` (PDFBOX-6322, PDFBox 3.0.9).

Tests the glyph name to Unicode mapping of the Adobe Glyph List.
"""

import pytest

from pypdfbox.fontbox.encoding.glyph_list import GlyphList


@pytest.fixture
def glyph_list() -> GlyphList:
    return GlyphList.get_adobe_glyph_list()


def test_underscore_ligatures(glyph_list: GlyphList) -> None:
    # Ligature names in the AGL underscore form, see section 2 of the AGL
    # specification: https://github.com/adobe-type-tools/agl-specification
    assert glyph_list.to_unicode("f_f") == "ff"
    assert glyph_list.to_unicode("f_i") == "fi"
    assert glyph_list.to_unicode("f_l") == "fl"
    assert glyph_list.to_unicode("f_f_i") == "ffi"
    assert glyph_list.to_unicode("f_f_l") == "ffl"
    assert glyph_list.to_unicode("T_h") == "Th"


def test_underscore_ligatures_with_suffix_and_uni_components(
    glyph_list: GlyphList,
) -> None:
    assert glyph_list.to_unicode("f_f_i.alt") == "ffi"
    assert glyph_list.to_unicode("uni0066_uni0069") == "fi"
    assert glyph_list.to_unicode("f_uni0069") == "fi"


def test_unresolvable_underscore_names(glyph_list: GlyphList) -> None:
    assert glyph_list.to_unicode("f__i") is None
    assert glyph_list.to_unicode("_") is None
    assert glyph_list.to_unicode("f_") is None
    assert glyph_list.to_unicode("_f") is None
    assert glyph_list.to_unicode("f_bogus") is None


def test_existing_names_unchanged(glyph_list: GlyphList) -> None:
    assert glyph_list.to_unicode("fi") == "ﬁ"
    assert glyph_list.to_unicode("ffi") == "ﬃ"
    assert glyph_list.to_unicode("A") == "A"
    assert glyph_list.to_unicode("underscore") == "_"
    assert glyph_list.to_unicode("five.lin") == "5"
    assert glyph_list.to_unicode("uni20AC") == "€"
