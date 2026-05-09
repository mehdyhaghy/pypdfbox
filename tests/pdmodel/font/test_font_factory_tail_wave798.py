from __future__ import annotations

from typing import Any, cast

from pypdfbox.fontbox.font_box_font import FontBoxFont
from pypdfbox.fontbox.font_mapper import FontMapper
from pypdfbox.fontbox.font_mapping import FontMapping
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory


class _RecordingMapper(FontMapper):
    def __init__(self) -> None:
        self.calls: list[tuple[str, PDFontDescriptor | None]] = []
        self.mapping = FontMapping(cast(FontBoxFont, object()), True)

    def get_true_type_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        return None

    def get_open_type_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        return None

    def get_font_box_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[FontBoxFont]:
        self.calls.append((base_font, font_descriptor))
        return self.mapping


def test_font_factory_mapper_hooks_delegate_to_active_mapper() -> None:
    mapper = _RecordingMapper()
    descriptor = PDFontDescriptor()
    try:
        PDFontFactory.set_font_mapper(mapper)

        assert PDFontFactory.get_font_mapper() is mapper
        assert (
            PDFontFactory.find_font_box_font("WaveTailFont", descriptor)
            is mapper.mapping
        )
        assert mapper.calls == [("WaveTailFont", descriptor)]
    finally:
        PDFontFactory.set_font_mapper(None)
