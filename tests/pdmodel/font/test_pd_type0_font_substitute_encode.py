"""PDType0Font.encode for a non-embedded CIDFontType2 under Identity-H.

Upstream ``PDType0Font.encode(int)`` delegates to
``PDCIDFontType2.encode``, which writes the substitute font's glyph id for
a non-embedded font (``cmap.getGlyphId(unicode)``). pypdfbox used to write
the codepoint itself, which ``code_to_gid`` then read back as a glyph id,
so the wrong glyph was shown.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


def _n(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def _non_embedded_type0(encoding: str = "Identity-H") -> PDType0Font:
    ros = COSDictionary()
    ros.set_item(_n("Registry"), COSString("Adobe"))
    ros.set_item(_n("Ordering"), COSString("Identity"))
    ros.set_item(_n("Supplement"), COSInteger.get(0))
    fd = COSDictionary()
    fd.set_item(_n("Type"), _n("FontDescriptor"))
    fd.set_name(_n("FontName"), "ArialMT")
    fd.set_int(_n("Flags"), 32)
    desc = COSDictionary()
    desc.set_item(_n("Type"), _n("Font"))
    desc.set_item(_n("Subtype"), _n("CIDFontType2"))
    desc.set_name(_n("BaseFont"), "ArialMT")
    desc.set_item(_n("CIDSystemInfo"), ros)
    desc.set_item(_n("FontDescriptor"), fd)
    descendants = COSArray()
    descendants.add(desc)
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Font"))
    d.set_item(_n("Subtype"), _n("Type0"))
    d.set_name(_n("BaseFont"), "ArialMT")
    d.set_item(_n("Encoding"), _n(encoding))
    d.set_item(_n("DescendantFonts"), descendants)
    return PDType0Font(d)


@pytest.mark.parametrize("encoding", ["Identity-H", "Identity-V"])
def test_encode_writes_substitute_glyph_id(encoding: str) -> None:
    font = _non_embedded_type0(encoding)
    descendant = font.get_descendant_font()
    for ch in " AB":
        encoded = font.encode(ch)
        assert encoded == descendant.encode(ord(ch))
        assert len(encoded) == 2
        assert int.from_bytes(encoded, "big") != ord(ch)


def test_encoded_code_round_trips_to_the_same_glyph() -> None:
    font = _non_embedded_type0()
    descendant = font.get_descendant_font()
    for ch in "AB":
        code = int.from_bytes(font.encode(ch), "big")
        assert descendant.code_to_gid(code) == code


def test_string_encode_concatenates_glyph_ids() -> None:
    font = _non_embedded_type0()
    assert font.encode("AB") == font.encode("A") + font.encode("B")


def test_missing_glyph_falls_back_to_notdef_without_caching() -> None:
    font = _non_embedded_type0()
    # U+E000 (private use) has no glyph in the bundled substitute
    assert font.encode("") == b"\x00\x00"
    assert 0xE000 not in font._codepoint_to_encoding_map
