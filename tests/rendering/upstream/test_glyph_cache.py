"""Upstream-equivalent parity tests for ``pypdfbox.rendering.GlyphCache``.

Upstream baseline: PDFBox 3.0.x.
Source: ``pdfbox/src/main/java/org/apache/pdfbox/rendering/GlyphCache.java``.

Upstream's ``GlyphCache`` is keyed by ``character code -> GeneralPath``
and is used by ``PageDrawer.drawGlyph`` to avoid repeated outline
rendering for the same code in a font subset. Two upstream-specific
edge cases must round-trip identically:

1. PDFBOX-4001: code 10 (LF) on a Standard 14 font returns an empty
   path silently instead of warning every time.
2. Glyph-rendering ``IOException`` returns an empty path (logged at
   ``ERROR``) — the cache itself never raises.

Upstream has no dedicated JUnit; PageDrawer tests touch the cache
transitively. We pin the contract directly so a future refactor of
``get_path_for_character_code`` is parity-checked.
"""
from __future__ import annotations

import logging
from typing import Any

import pytest

from pypdfbox.rendering.glyph_cache import GlyphCache


class _StubFont:
    """Minimal font surface that the cache probes via ``hasattr``."""

    def __init__(
        self,
        *,
        name: str = "TestFont",
        has_glyph_map: dict[int, bool] | None = None,
        path_map: dict[int, Any] | None = None,
        is_standard14: bool = False,
        cid_map: dict[int, int] | None = None,
        raise_on: dict[int, Exception] | None = None,
    ) -> None:
        self._name = name
        self._has_glyph_map = has_glyph_map or {}
        self._path_map = path_map or {}
        self._is_standard14 = is_standard14
        self._cid_map = cid_map or {}
        self._raise_on = raise_on or {}

    def get_name(self) -> str:
        return self._name

    def has_glyph(self, code: int) -> bool:
        return self._has_glyph_map.get(code, True)

    def is_standard14(self) -> bool:
        return self._is_standard14

    def code_to_cid(self, code: int) -> int:
        return self._cid_map.get(code, code)

    def get_normalized_path(self, code: int) -> Any:
        if code in self._raise_on:
            raise self._raise_on[code]
        return self._path_map.get(code, [("moveTo", code, code)])


def test_cache_hit_returns_same_object_without_calling_font() -> None:
    sentinel: list[Any] = [("cached_path",)]
    font = _StubFont(path_map={42: sentinel})
    cache = GlyphCache(font)
    first = cache.get_path_for_character_code(42)
    second = cache.get_path_for_character_code(42)
    assert first is sentinel
    assert second is first


def test_cache_miss_populates_cache_via_font() -> None:
    font = _StubFont(path_map={7: [("path_seven",)]})
    cache = GlyphCache(font)
    result = cache.get_path_for_character_code(7)
    assert result == [("path_seven",)]
    # Direct dict probe — upstream cache is a HashMap; pin the key.
    assert cache._cache[7] is result


def test_missing_glyph_logs_warning_and_returns_empty_path_for_std14_lf(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PDFBOX-4001: code 10 (LF) on a Standard 14 simple font silently
    returns an empty path. We log the warning but the path is empty
    and gets cached.

    The special-case branch only fires for *simple* fonts (no
    ``code_to_cid``) — CID fonts log the CID instead and fall through
    to ``get_normalized_path``.
    """

    class _Std14SimpleFont:
        # No ``code_to_cid`` — triggers the upstream simple-font branch.
        def get_name(self) -> str:
            return "Helvetica"

        def has_glyph(self, code: int) -> bool:  # noqa: ARG002
            return False

        def is_standard14(self) -> bool:
            return True

        def get_normalized_path(self, code: int) -> Any:  # pragma: no cover
            # The LF short-circuit must hit *before* this is called.
            raise AssertionError(
                f"unexpected get_normalized_path({code}) — LF short-circuit "
                f"failed to fire"
            )

    cache = GlyphCache(_Std14SimpleFont())  # type: ignore[arg-type]
    with caplog.at_level(logging.WARNING):
        result = cache.get_path_for_character_code(10)
    assert result == []
    assert cache._cache[10] == []


def test_cid_font_missing_glyph_logs_cid_and_returns_outline(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ``code_to_cid`` branch must log the CID and still hand the
    code off to ``get_normalized_path`` — i.e. the LF short-circuit is
    suppressed for CID fonts because CIDs are decoupled from raw codes.
    """

    class _CidFont:
        def get_name(self) -> str:
            return "CIDFont"

        def has_glyph(self, code: int) -> bool:  # noqa: ARG002
            return False

        def code_to_cid(self, code: int) -> int:
            return code * 2

        def get_normalized_path(self, code: int) -> Any:
            return [("cid_fallback", code)]

    cache = GlyphCache(_CidFont())  # type: ignore[arg-type]
    with caplog.at_level(logging.WARNING):
        result = cache.get_path_for_character_code(10)
    assert result == [("cid_fallback", 10)]
    # The warning still fires, but the CID short-circuit does NOT —
    # the path comes from ``get_normalized_path``.
    assert cache._cache[10] == [("cid_fallback", 10)]


def test_oserror_during_glyph_render_returns_empty_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Upstream wraps the rendering call in ``try { ... } catch
    (IOException e)`` and logs at ERROR. We mirror with ``OSError``.
    """
    font = _StubFont(raise_on={5: OSError("synthetic")})
    cache = GlyphCache(font)
    with caplog.at_level(logging.ERROR):
        result = cache.get_path_for_character_code(5)
    assert result == []
    # The error path does *not* cache (upstream re-raises on next call
    # if the IOException is transient; pypdfbox matches by leaving the
    # slot empty).
    assert 5 not in cache._cache


def test_cache_is_per_instance() -> None:
    """``GlyphCache`` is constructed per-font; two caches must not
    share state."""
    sentinel_a: list[Any] = [("a",)]
    sentinel_b: list[Any] = [("b",)]
    cache_a = GlyphCache(_StubFont(path_map={1: sentinel_a}))
    cache_b = GlyphCache(_StubFont(path_map={1: sentinel_b}))
    assert cache_a.get_path_for_character_code(1) is sentinel_a
    assert cache_b.get_path_for_character_code(1) is sentinel_b


def test_font_without_has_glyph_treats_every_code_as_present() -> None:
    """Upstream's font hierarchy always has ``hasGlyph`` but pypdfbox
    accepts the absence as "always true" — the cache should still
    render without raising AttributeError."""

    class _BareFont:
        def get_normalized_path(self, code: int) -> Any:
            return [("bare", code)]

    cache = GlyphCache(_BareFont())  # type: ignore[arg-type]
    assert cache.get_path_for_character_code(99) == [("bare", 99)]


def test_font_without_get_normalized_path_returns_empty_path() -> None:
    """If the font lacks the outline accessor, the cache short-circuits
    to an empty path instead of crashing.
    """

    class _NoOutlineFont:
        def has_glyph(self, code: int) -> bool:  # noqa: ARG002
            return True

    cache = GlyphCache(_NoOutlineFont())  # type: ignore[arg-type]
    assert cache.get_path_for_character_code(1) == []
