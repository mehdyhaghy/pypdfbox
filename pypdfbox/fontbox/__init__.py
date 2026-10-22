from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .cid_font_mapping import CIDFontMapping
    from .encoded_font import EncodedFont
    from .encoding import (
        Encoding,
        GlyphList,
        MacExpertEncoding,
        MacRomanEncoding,
        StandardEncoding,
        SymbolEncoding,
        WinAnsiEncoding,
        ZapfDingbatsEncoding,
    )
    from .font_box_font import FontBoxFont
    from .font_format import FontFormat
    from .font_info import FontInfo
    from .font_mapper import (
        DefaultFontMapper,
        FontMapper,
        Standard14FontWrapper,
    )
    from .font_mappers import FontMappers
    from .font_mapping import FontMapping
    from .font_provider import FontProvider

__getattr__, __dir__ = _attach(
    __name__,
    {
        "CIDFontMapping": ".cid_font_mapping",
        "EncodedFont": ".encoded_font",
        "Encoding": ".encoding",
        "GlyphList": ".encoding",
        "MacExpertEncoding": ".encoding",
        "MacRomanEncoding": ".encoding",
        "StandardEncoding": ".encoding",
        "SymbolEncoding": ".encoding",
        "WinAnsiEncoding": ".encoding",
        "ZapfDingbatsEncoding": ".encoding",
        "FontBoxFont": ".font_box_font",
        "FontFormat": ".font_format",
        "FontInfo": ".font_info",
        "DefaultFontMapper": ".font_mapper",
        "FontMapper": ".font_mapper",
        "Standard14FontWrapper": ".font_mapper",
        "FontMappers": ".font_mappers",
        "FontMapping": ".font_mapping",
        "FontProvider": ".font_provider",
    },
)

__all__ = [
    "CIDFontMapping",
    "DefaultFontMapper",
    "EncodedFont",
    "Encoding",
    "FontBoxFont",
    "FontFormat",
    "FontInfo",
    "FontMapper",
    "FontMappers",
    "FontMapping",
    "FontProvider",
    "GlyphList",
    "MacExpertEncoding",
    "MacRomanEncoding",
    "Standard14FontWrapper",
    "StandardEncoding",
    "SymbolEncoding",
    "WinAnsiEncoding",
    "ZapfDingbatsEncoding",
]
