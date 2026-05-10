"""Ported from upstream PDFBox 3.0.x ``TestCMap.java``.

Source: ``fontbox/src/test/java/org/apache/fontbox/cmap/TestCMap.java``.
"""

from __future__ import annotations

from pypdfbox.fontbox.cmap import CMap


def test_lookup() -> None:
    """Direct port of upstream ``testLookup`` — exercises the
    ``addCharMapping`` / ``toUnicode(byte[])`` round-trip with a single
    out-of-ASCII byte.
    """
    bs = bytes([200])
    cmap = CMap()
    cmap.add_char_mapping(bs, "a")
    assert cmap.to_unicode_bytes(bs) == "a"


# Skipped: testPDFBox3997 requires loading ``target/fonts/NotoEmoji-Regular.ttf``
# via ``TTFParser`` and exercising ``CmapLookup.getGlyphId`` rather than ``CMap``
# itself. The TrueType cmap subtable plumbing lives in the ``ttf`` package and is
# covered by tests/fontbox/ttf/ — porting it here would duplicate that surface
# and add a binary fixture dependency.
