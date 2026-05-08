from __future__ import annotations

from typing import Any, cast

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.text import PDFTextStripper


class _TypedFontResources:
    def __init__(self, font: PDType1Font) -> None:
        self.font = font

    def get_font(self, _name: COSName) -> PDType1Font:
        return self.font


class _TypedFontPage:
    def __init__(self, resources: _TypedFontResources) -> None:
        self._resources = resources

    def get_resources(self) -> _TypedFontResources:
        return self._resources


def test_get_font_for_accepts_typed_resource_cache_entries() -> None:
    font = PDType1Font()
    stripper = PDFTextStripper()
    stripper._active_page = cast(Any, _TypedFontPage(_TypedFontResources(font)))

    assert stripper._get_font_for("F1") is font
    assert stripper._get_font_for("F1") is font


def test_get_cmap_for_font_accepts_typed_resource_cache_entries() -> None:
    font = PDType1Font()
    stripper = PDFTextStripper()
    stripper._active_page = cast(Any, _TypedFontPage(_TypedFontResources(font)))

    assert stripper._get_cmap_for_font("F1") is None
    assert "F1" in stripper._cmap_cache
