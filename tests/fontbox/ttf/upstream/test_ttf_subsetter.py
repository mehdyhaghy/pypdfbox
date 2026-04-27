"""Ported upstream tests for :class:`TTFSubsetter`.

Translated from
``fontbox/src/test/java/org/apache/fontbox/ttf/TTFSubsetterTest.java``
(PDFBox 3.0). Skips the parts of upstream that do byte-for-byte
glyph-table comparison or rely on system-installed fonts (SimHei,
DejaVuSansMono, NotoMono, Keyboard) we don't ship as fixtures.

Tests retained:

* ``testEmptySubset`` (PDFBOX-2854): empty subset emits .notdef-only TTF.
* ``testEmptySubset2`` (PDFBOX-2854): same with explicit keep-tables list.
* ``testNonEmptySubset`` (PDFBOX-2854): one-glyph subset round-trips.
* ``testPDFBox3757``: subset with mixed codepoints round-trips through
  the cmap (we do not assert the exact ``post`` table glyph-name order,
  which is an upstream-specific detail of their handcrafted post-table
  builder; fontTools handles names internally).

Tests skipped (and why):

* ``testPDFBox3319`` — needs system-installed SimHei.
* ``testPDFBox3379`` — needs DejaVuSansMono fixture not in our corpus.
* ``testPDFBox5728`` — needs NotoMono-Regular fixture.
* ``testPDFBox5230`` — relies on upstream's ``forceInvisible`` (an
  embedder-level concern; not part of the library-first wrapper API).
* ``testPDFBox6015`` — exercises a 0/1-cmap font fixture (Keyboard.ttf)
  that we don't ship.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


def _ttlib(buf: bytes):
    import fontTools.ttLib as ttLib  # noqa: PLC0415

    return ttLib.TTFont(io.BytesIO(buf))


def _name_to_gid(tt, name: str) -> int:
    order = tt.getGlyphOrder()
    return order.index(name) if name in order else 0


# ---------- ported tests --------------------------------------------------


def test_empty_subset(liberation_sans: TrueTypeFont) -> None:
    """PDFBOX-2854: empty subset retains only ``.notdef``."""
    subsetter = TTFSubsetter(liberation_sans)
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    tt = _ttlib(baos.getvalue())
    assert tt["maxp"].numGlyphs == 1
    assert _name_to_gid(tt, ".notdef") == 0


def test_empty_subset2(liberation_sans: TrueTypeFont) -> None:
    """PDFBOX-2854 variant: empty subset with the upstream
    ``TrueTypeEmbedder`` keep-tables list."""
    tables = [
        "head",
        "hhea",
        "loca",
        "maxp",
        "cvt ",
        "prep",
        "glyf",
        "hmtx",
        "fpgm",
        "gasp",
    ]
    subsetter = TTFSubsetter(liberation_sans, tables)
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    tt = _ttlib(baos.getvalue())
    assert tt["maxp"].numGlyphs == 1
    assert _name_to_gid(tt, ".notdef") == 0


def test_non_empty_subset(liberation_sans: TrueTypeFont) -> None:
    """PDFBOX-2854: one-glyph subset retains ``.notdef`` plus ``a``."""
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.add(ord("a"))
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    tt = _ttlib(baos.getvalue())
    assert tt["maxp"].numGlyphs == 2
    assert _name_to_gid(tt, ".notdef") == 0
    assert _name_to_gid(tt, "a") == 1
    # Advance width must survive subsetting unchanged.
    full_metrics = liberation_sans._tt["hmtx"].metrics  # noqa: SLF001
    assert tt["hmtx"].metrics["a"][0] == full_metrics["a"][0]


def test_pdfbox_3757(liberation_sans: TrueTypeFont) -> None:
    """PDFBOX-3757: subset with mixed codepoints round-trips through
    the cmap. Upstream additionally asserts a specific glyph order in
    the ``post`` table; we drop that — fontTools owns ``post`` naming
    and the glyph-order detail is not part of the library-first
    contract."""
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.add(ord("Ö"))
    subsetter.add(0x200A)
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    tt = _ttlib(baos.getvalue())
    # .notdef + the requested glyphs + composite parts (O + dieresis).
    assert tt["maxp"].numGlyphs >= 3
    cmap = tt["cmap"].getBestCmap()
    assert ord("Ö") in cmap
    assert 0x200A in cmap


# ---------- intentionally skipped (system fonts not shipped) ------------


def test_pdfbox_3319_simhei() -> None:
    pytest.skip("PDFBOX-3319 needs system-installed SimHei font")


def test_pdfbox_3379_dejavu_mono() -> None:
    pytest.skip("PDFBOX-3379 needs DejaVuSansMono fixture not in corpus")


def test_pdfbox_5728_noto_mono() -> None:
    pytest.skip("PDFBOX-5728 needs NotoMono-Regular fixture not in corpus")


def test_pdfbox_5230_force_invisible() -> None:
    pytest.skip("forceInvisible is an embedder-level concern, not in library-first wrapper")


def test_pdfbox_6015_keyboard_ttf() -> None:
    pytest.skip("PDFBOX-6015 needs Keyboard.ttf fixture not in corpus")
