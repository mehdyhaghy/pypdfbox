"""Tests for :class:`FontProvider`.

The default pypdfbox build doesn't ship a concrete :class:`FontProvider`
(upstream's ``FileSystemFontProvider`` is deferred — see CHANGES.md).
These tests pin the abstract contract so pluggable providers stay
predictable.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_info import FontInfo
from pypdfbox.fontbox.font_provider import FontProvider


class _StubInfo(FontInfo):
    def __init__(self, name: str) -> None:
        self._name = name

    def get_post_script_name(self) -> str:
        return self._name

    def get_format(self) -> FontFormat:
        return FontFormat.TTF

    def get_cid_system_info(self) -> object | None:
        return None

    def get_font(self) -> object:  # type: ignore[override]
        # Tests don't materialise the font; FontInfo.get_font is only
        # called when the mapper actually needs to load metrics.
        raise NotImplementedError

    def get_family_class(self) -> int:
        return -1

    def get_weight_class(self) -> int:
        return -1

    def get_code_page_range1(self) -> int:
        return 0

    def get_code_page_range2(self) -> int:
        return 0

    def get_mac_style(self) -> int:
        return -1

    def get_panose(self) -> object | None:
        return None


class _ListProvider(FontProvider):
    def __init__(self, infos: list[FontInfo], debug: str | None) -> None:
        self._infos = infos
        self._debug = debug

    def to_debug_string(self) -> str | None:
        return self._debug

    def get_font_info(self) -> Sequence[FontInfo]:
        return self._infos


# ---------------------------------------------------------------------------
# Abstract surface
# ---------------------------------------------------------------------------


def test_font_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        FontProvider()  # type: ignore[abstract]


def test_partial_subclass_still_abstract() -> None:
    class _OnlyDebug(FontProvider):
        def to_debug_string(self) -> str | None:
            return None

    with pytest.raises(TypeError):
        _OnlyDebug()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Concrete subclass round-trip
# ---------------------------------------------------------------------------


def test_get_font_info_returns_supplied_sequence() -> None:
    a = _StubInfo("FontA")
    b = _StubInfo("FontB")
    provider = _ListProvider([a, b], debug="2 fonts on disk")
    infos = provider.get_font_info()
    assert list(infos) == [a, b]


def test_to_debug_string_passes_through() -> None:
    provider = _ListProvider([], debug="diagnostics body")
    assert provider.to_debug_string() == "diagnostics body"


def test_to_debug_string_allows_none() -> None:
    """Upstream contract: ``None`` is allowed."""
    provider = _ListProvider([], debug=None)
    assert provider.to_debug_string() is None


def test_get_font_info_can_be_empty_sequence() -> None:
    provider = _ListProvider([], debug=None)
    assert list(provider.get_font_info()) == []
