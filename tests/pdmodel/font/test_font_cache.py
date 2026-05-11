"""Tests for :mod:`pypdfbox.pdmodel.font.font_cache`.

No upstream JUnit test exists — :class:`FontCache` is exercised only
through :class:`FileSystemFontProvider`. We cover put/get round-trip,
missing-key lookup, and the pypdfbox-specific :meth:`clear` extension.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.font.font_cache import FontCache


class _FakeFontInfo:
    """Minimal hashable stand-in for :class:`FontInfo`."""

    def __init__(self, name: str) -> None:
        self._name: str = name

    def __hash__(self) -> int:
        return hash(self._name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _FakeFontInfo) and other._name == self._name


class _FakeFont:
    """Minimal stand-in for :class:`FontBoxFont` — weakref-compatible."""


@pytest.fixture
def cache() -> FontCache:
    return FontCache()


def test_add_then_get_round_trip(cache: FontCache) -> None:
    info = _FakeFontInfo("Arial")
    font: Any = _FakeFont()
    cache.add_font(info, font)
    assert cache.get_font(info) is font


def test_get_missing_returns_none(cache: FontCache) -> None:
    assert cache.get_font(_FakeFontInfo("MissingFont")) is None


def test_clear_drops_all_entries(cache: FontCache) -> None:
    info = _FakeFontInfo("Arial")
    cache.add_font(info, _FakeFont())
    # The font is held weakly — we need a strong ref for the lookup to
    # succeed before clear.
    keepalive: Any = _FakeFont()
    info2 = _FakeFontInfo("Helvetica")
    cache.add_font(info2, keepalive)
    assert cache.get_font(info2) is keepalive
    cache.clear()
    assert cache.get_font(info2) is None


def test_strong_fallback_for_slotted_objects() -> None:
    """Objects without ``__weakref__`` route to the strong-ref fallback."""

    class _NoWeakRef:
        __slots__ = ()

    cache = FontCache()
    info = _FakeFontInfo("Slotted")
    obj: Any = _NoWeakRef()
    cache.add_font(info, obj)
    assert cache.get_font(info) is obj
