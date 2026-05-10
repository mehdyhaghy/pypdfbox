"""Upstream-equivalent tests for :class:`TrueTypeFont`.

Apache PDFBox 3.0.x doesn't ship a dedicated ``TrueTypeFontTest.java``;
the ``TrueTypeFont`` accessors are exercised in
``fontbox/src/test/java/org/apache/fontbox/ttf/TestTTFParser.java`` —
specifically ``testPostTable`` (around line 68) which walks the
``cmap`` / ``post`` tables of LiberationSans to check WGL4-name
round-tripping. This file ports that flow against the pypdfbox
``TrueTypeFont`` surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.cmap_table import CmapTable

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


def test_post_table_round_trips_wgl4_names(liberation_sans: TrueTypeFont) -> None:
    """Port of TestTTFParser.testPostTable (line 68).

    Walks the Windows-Unicode-BMP cmap subtable for the WGL4 trademark /
    euro codepoints, then asserts they round-trip through the post
    table's glyph-name array.
    """
    cmap_table = liberation_sans.get_cmap()
    assert cmap_table is not None

    # PDFBox's resolver prefers ``Unicode-2.0-Full`` (platform 0,
    # encoding 4) on Liberation Sans before falling back to the
    # Windows-Unicode-BMP subtable upstream's test selects directly. We
    # accept either pair — the data they index is identical for BMP
    # codepoints.
    assert (cmap_table.get_platform_id(), cmap_table.get_platform_encoding_id()) in {
        (CmapTable.PLATFORM_UNICODE, CmapTable.ENCODING_UNICODE_2_0_FULL),
        (CmapTable.PLATFORM_UNICODE, CmapTable.ENCODING_UNICODE_2_0_BMP),
        (CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_UNICODE_FULL),
        (CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_UNICODE_BMP),
    }

    post = liberation_sans.get_post_script()
    assert post is not None
    glyph_names = post.get_glyph_names()
    assert glyph_names is not None

    # WGL4: trademark sign U+2122.
    gid = cmap_table.get_glyph_id(0x2122)
    assert glyph_names[gid] == "trademark"
    # Additional name: euro sign U+20AC.
    gid = cmap_table.get_glyph_id(0x20AC)
    assert glyph_names[gid] == "Euro"


def test_name_to_gid_round_trips_post_names(liberation_sans: TrueTypeFont) -> None:
    """Equivalent of ``font.nameToGID(post.getGlyphNames()[gid])``.

    Upstream's ``nameToGID`` looks the name up in the post table; this
    test asserts the round-trip from gid -> name (via the post table)
    -> gid (via ``name_to_gid``) is identity for known glyphs.
    """
    post = liberation_sans.get_post_script()
    assert post is not None
    glyph_names = post.get_glyph_names()
    assert glyph_names is not None
    # Sample a few non-.notdef gids and round-trip each one.
    for gid in (1, 5, 10, 50):
        if gid >= len(glyph_names):
            continue
        name = glyph_names[gid]
        if name in {".notdef", "nonmarkingreturn", "null"}:
            continue
        assert liberation_sans.name_to_gid(name) == gid


def test_get_unicode_cmap_lookup_returns_real_glyph_for_known_chars(
    liberation_sans: TrueTypeFont,
) -> None:
    """Port of ``font.getUnicodeCmapLookup().getGlyphId(...)`` usage.

    The lookup must return non-zero GIDs for codepoints actually in the
    font (matches upstream behaviour where a missing-glyph result is the
    flag for "not found").
    """
    lookup = liberation_sans.get_unicode_cmap_lookup()
    assert lookup is not None
    assert lookup.get_glyph_id(ord("A")) > 0
    assert lookup.get_glyph_id(0x2122) > 0  # trademark
    assert lookup.get_glyph_id(0x20AC) > 0  # euro
