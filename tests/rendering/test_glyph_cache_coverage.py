"""Coverage-boost tests for ``pypdfbox.rendering.glyph_cache``.

Targets the uncovered branches in ``GlyphCache.get_path_for_character_code``:
- cache-hit early return
- CID-aware warning path (font with ``code_to_cid``)
- non-CID warning path (font without ``code_to_cid``)
- Standard14 LF (code 10) empty-path special-case (PDFBOX-4001)
- font missing ``get_normalized_path`` falls back to ``_empty_path()``
- ``OSError`` from glyph rendering -> empty path returned, not cached
- ``_empty_path()`` helper returns an empty list
"""

from __future__ import annotations

import logging

from pypdfbox.rendering.glyph_cache import GlyphCache, _empty_path


class _FontWithCID:
    """A vector font that always reports the glyph missing and exposes ``code_to_cid``."""

    def __init__(self, name: str = "CIDFont") -> None:
        self._name = name

    def has_glyph(self, code: int) -> bool:
        return False

    def code_to_cid(self, code: int) -> int:
        return code + 0x1000

    def get_name(self) -> str:
        return self._name

    def get_normalized_path(self, code: int) -> list:
        return [("M", 0.0, 0.0), ("L", float(code), float(code))]


class _FontStd14NoCID:
    """A non-CID font reporting Standard14 status; missing-glyph triggers warning."""

    def __init__(self, std14: bool = True) -> None:
        self._std14 = std14

    def has_glyph(self, code: int) -> bool:
        return False

    def is_standard14(self) -> bool:
        return self._std14

    def get_name(self) -> str:
        return "Std14Font"

    def get_normalized_path(self, code: int) -> list:
        # Should NOT be reached for code == 10 + std14 (early-return empty path),
        # but is reached for non-LF missing glyphs in std14 fonts.
        return [("nonstd14",)]


class _FontMinimal:
    """Has no ``has_glyph`` and no ``get_normalized_path``; falls through to empty path."""

    pass


class _FontRaisesOSError:
    """``get_normalized_path`` raises ``OSError`` -> empty path returned but not cached."""

    def has_glyph(self, code: int) -> bool:
        return True

    def get_normalized_path(self, code: int) -> list:
        raise OSError("simulated rendering failure")


class _FontHappy:
    """A font where the glyph is present and a real path is produced (cache hit test)."""

    def __init__(self) -> None:
        self.calls = 0

    def has_glyph(self, code: int) -> bool:
        return True

    def get_normalized_path(self, code: int) -> list:
        self.calls += 1
        return [("M", float(code), 0.0)]


def test_empty_path_helper_returns_empty_list() -> None:
    assert _empty_path() == []


def test_get_path_caches_and_returns_same_object() -> None:
    font = _FontHappy()
    cache = GlyphCache(font)
    first = cache.get_path_for_character_code(65)
    second = cache.get_path_for_character_code(65)
    assert first is second
    assert font.calls == 1, "second call must hit the cache, not the font"


def test_missing_glyph_with_cid_logs_cid_warning(caplog) -> None:
    font = _FontWithCID(name="MyCIDFont")
    cache = GlyphCache(font)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.rendering.glyph_cache"):
        path = cache.get_path_for_character_code(0x42)
    # CID branch still proceeds to ``get_normalized_path``.
    assert path == [("M", 0.0, 0.0), ("L", 66.0, 66.0)]
    msgs = " ".join(rec.message for rec in caplog.records)
    assert "CID" in msgs
    assert "MyCIDFont" in msgs


def test_missing_glyph_without_cid_in_std14_lf_returns_empty_path() -> None:
    font = _FontStd14NoCID(std14=True)
    cache = GlyphCache(font)
    path = cache.get_path_for_character_code(10)
    assert path == []
    # And it was cached.
    assert cache.get_path_for_character_code(10) is path


def test_missing_glyph_non_lf_std14_still_calls_get_normalized_path(caplog) -> None:
    font = _FontStd14NoCID(std14=True)
    cache = GlyphCache(font)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.rendering.glyph_cache"):
        path = cache.get_path_for_character_code(33)  # non-LF
    assert path == [("nonstd14",)]
    # Warning logged for missing glyph.
    assert any("No glyph for code" in rec.message for rec in caplog.records)


def test_missing_glyph_without_cid_non_std14_does_not_short_circuit(caplog) -> None:
    font = _FontStd14NoCID(std14=False)
    cache = GlyphCache(font)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.rendering.glyph_cache"):
        path = cache.get_path_for_character_code(10)  # LF but non-std14
    # Non-std14 LF still gets the upstream's normalized path call.
    assert path == [("nonstd14",)]
    assert any("No glyph for code" in rec.message for rec in caplog.records)


def test_minimal_font_without_get_normalized_path_returns_empty_list() -> None:
    cache = GlyphCache(_FontMinimal())
    path = cache.get_path_for_character_code(7)
    assert path == []


def test_oserror_during_rendering_returns_empty_path_not_cached(caplog) -> None:
    font = _FontRaisesOSError()
    cache = GlyphCache(font)
    with caplog.at_level(logging.ERROR, logger="pypdfbox.rendering.glyph_cache"):
        path = cache.get_path_for_character_code(99)
    assert path == []
    assert any("Glyph rendering failed" in rec.message for rec in caplog.records)
    # The empty-path returned on error is NOT stored, so a second call re-raises
    # the same OSError path (returning another empty list, but not the cached one).
    assert 99 not in cache._cache
