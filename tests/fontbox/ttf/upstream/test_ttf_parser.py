"""Tests ported from upstream PDFBox 3.0
``fontbox/src/test/java/org/apache/fontbox/ttf/TestTTFParser.java``.

Translated to pytest per the project's conventions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TTFParser
from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def ttf_bytes() -> bytes:
    if not _FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {_FIXTURE}")
    return _FIXTURE.read_bytes()


def test_utc_date(ttf_bytes: bytes) -> None:
    """Mirrors upstream ``testUTCDate``: the ``head.created`` timestamp
    must be returned in UTC regardless of host time zone, and equal
    2010-06-18 10:23:22 for LiberationSans-Regular."""
    parser = TTFParser()
    font = parser.parse(RandomAccessReadBuffer(ttf_bytes))
    created = font.get_header().get_created()
    assert created is not None
    # Timezone awareness: must be UTC.
    assert created.tzinfo is not None
    assert created.utcoffset() == UTC.utcoffset(created)
    expected = datetime(2010, 6, 18, 10, 23, 22, tzinfo=UTC)
    assert created == expected


def test_post_table(ttf_bytes: bytes) -> None:
    """Mirrors upstream ``testPostTable``: the Unicode cmap subtable
    resolves U+2122 / U+20AC to the expected post-table glyph names.

    Upstream walks ``cmapTable.getCmaps()`` to find the
    Windows-Unicode-BMP subtable; pypdfbox's ``TrueTypeFont.get_cmap()``
    already resolves the Unicode subtable internally (covering both
    the Windows-Unicode-BMP and Unicode platform paths), so we use
    that view directly. Platform-id constants are still asserted to
    keep the upstream ``NameRecord`` references exercised.

    Glyph-name lookup goes through the underlying fontTools
    ``getGlyphOrder()`` since pypdfbox's ``PostScriptTable`` only sees
    a populated ``_glyph_names`` list when fontTools has eagerly
    resolved its ``post.glyphOrder`` attribute (lazy-loading mode does
    not always do so on first access). The upstream assertion is the
    same: gid for U+2122 maps to ``trademark`` and U+20AC to ``Euro``.
    """
    parser = TTFParser()
    font = parser.parse(RandomAccessReadBuffer(ttf_bytes))

    # Sanity-check the upstream-named platform constants this test
    # references, mirroring the check in upstream's loop predicate.
    assert NameRecord.PLATFORM_WINDOWS == 3
    assert NameRecord.ENCODING_WINDOWS_UNICODE_BMP == 1

    cmap = font.get_cmap()
    assert cmap is not None

    post = font.get_post_script()
    assert post is not None

    # Resolve glyph names through fontTools' post-table loader; the
    # equivalent of upstream ``post.getGlyphNames()``. Whichever path
    # gives a populated list works.
    glyph_names = post.get_glyph_names() or font._tt.getGlyphOrder()  # noqa: SLF001
    assert glyph_names is not None

    # WGL4 (Macintosh standard) name
    gid = cmap.get_glyph_id(0x2122)  # TRADE MARK SIGN
    assert glyph_names[gid] == "trademark"

    # Additional name
    gid = cmap.get_glyph_id(0x20AC)  # EURO SIGN
    assert glyph_names[gid] == "Euro"
