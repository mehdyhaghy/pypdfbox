"""Tests for :class:`pypdfbox.fontbox.ttf.GlyphTable`.

Loads the bundled LiberationSans-Regular fixture and exercises the
PDFBox-shaped accessors (``get_glyph`` / ``get_glyphs`` / ``set_glyphs``)
to confirm parity with upstream behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import GlyphData, GlyphTable, TrueTypeFont

FIXTURE = (
    Path(__file__).resolve().parents[2]
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


@pytest.fixture(scope="module")
def glyph_table(liberation_sans: TrueTypeFont) -> GlyphTable:
    gt = liberation_sans.get_glyph_table()
    assert gt is not None
    return gt


# ---------- table presence -------------------------------------------------


def test_glyph_table_is_present(liberation_sans: TrueTypeFont) -> None:
    gt = liberation_sans.get_glyph_table()
    assert gt is not None
    assert isinstance(gt, GlyphTable)


def test_tag_constant() -> None:
    assert GlyphTable.TAG == "glyf"


def test_glyph_table_is_cached(liberation_sans: TrueTypeFont) -> None:
    a = liberation_sans.get_glyph_table()
    b = liberation_sans.get_glyph_table()
    assert a is b


# ---------- get_glyph ------------------------------------------------------


def test_get_glyph_zero_is_notdef(glyph_table: GlyphTable) -> None:
    g = glyph_table.get_glyph(0)
    assert g is not None
    assert isinstance(g, GlyphData)


def test_get_glyph_returns_none_for_negative_gid(glyph_table: GlyphTable) -> None:
    assert glyph_table.get_glyph(-1) is None


def test_get_glyph_returns_none_for_out_of_range_gid(
    liberation_sans: TrueTypeFont, glyph_table: GlyphTable
) -> None:
    assert glyph_table.get_glyph(liberation_sans.get_number_of_glyphs()) is None
    assert glyph_table.get_glyph(10**9) is None


def test_get_glyph_caches_results(glyph_table: GlyphTable) -> None:
    # First call materialises; second call must return the same instance.
    a = glyph_table.get_glyph(1)
    b = glyph_table.get_glyph(1)
    assert a is b


# ---------- get_glyphs / set_glyphs ----------------------------------------


def test_get_glyphs_returns_one_per_gid(
    liberation_sans: TrueTypeFont, glyph_table: GlyphTable
) -> None:
    glyphs = glyph_table.get_glyphs()
    assert len(glyphs) == liberation_sans.get_number_of_glyphs()
    for g in glyphs[:10]:
        assert isinstance(g, GlyphData)


def test_set_glyphs_replaces_cache() -> None:
    # Use a tiny synthetic table to avoid touching the module-scoped fixture.
    gt = GlyphTable()
    gt._num_glyphs = 3  # noqa: SLF001
    gt._glyphs = [None, None, None]  # noqa: SLF001
    placeholder = GlyphData()
    gt.set_glyphs([placeholder, placeholder, placeholder])
    # All slots populated -> cached count should match.
    assert gt._cached == 3  # noqa: SLF001
    assert gt._glyphs == [placeholder, placeholder, placeholder]  # noqa: SLF001
    gt.set_glyphs(None)
    assert gt._glyphs is None  # noqa: SLF001
    assert gt._cached == 0  # noqa: SLF001


# ---------- TrueTypeFont convenience accessor ------------------------------


def test_true_type_font_get_glyph_delegates(
    liberation_sans: TrueTypeFont,
) -> None:
    g = liberation_sans.get_glyph(0)
    assert g is not None
    assert isinstance(g, GlyphData)


def test_true_type_font_get_glyph_out_of_range_is_none(
    liberation_sans: TrueTypeFont,
) -> None:
    assert liberation_sans.get_glyph(-1) is None
    assert liberation_sans.get_glyph(liberation_sans.get_number_of_glyphs()) is None


# ---------- get_glyph_data (alias mirroring upstream private accessor) -----


def test_get_glyph_data_delegates_to_get_glyph(glyph_table: GlyphTable) -> None:
    # Upstream ``getGlyphData(int, int)`` is the private worker reached
    # through ``getGlyph``; the port exposes a public alias that returns
    # the same cached :class:`GlyphData` instance.
    a = glyph_table.get_glyph(0)
    b = glyph_table.get_glyph_data(0)
    assert b is not None
    assert b is a
    assert isinstance(b, GlyphData)


def test_get_glyph_data_returns_none_for_out_of_range(
    liberation_sans: TrueTypeFont, glyph_table: GlyphTable
) -> None:
    assert glyph_table.get_glyph_data(-1) is None
    n = liberation_sans.get_number_of_glyphs()
    assert glyph_table.get_glyph_data(n) is None
