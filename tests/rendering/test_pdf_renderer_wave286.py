from __future__ import annotations

from typing import Any, cast

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.rendering.pdf_renderer import PDFRenderer


class _TypedFontResources:
    def __init__(self, font: PDType1Font) -> None:
        self.font = font

    def get_font(self, _name: COSName) -> PDType1Font:
        return self.font


def test_resolve_font_accepts_typed_resource_cache_entries() -> None:
    font = PDType1Font()
    renderer = PDFRenderer(cast(Any, object()))
    renderer._resources = cast(Any, _TypedFontResources(font))

    assert renderer._resolve_font(COSName.get_pdf_name("F1")) is font
    assert renderer._resolve_font(COSName.get_pdf_name("F1")) is font
