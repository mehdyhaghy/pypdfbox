from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .built_in_encoding import BuiltInEncoding
    from .encoding import Encoding
    from .glyph_list import GlyphList
    from .mac_expert_encoding import MacExpertEncoding
    from .mac_roman_encoding import MacRomanEncoding
    from .standard_encoding import StandardEncoding
    from .symbol_encoding import SymbolEncoding
    from .win_ansi_encoding import WinAnsiEncoding
    from .zapf_dingbats_encoding import ZapfDingbatsEncoding

__getattr__, __dir__ = _attach(
    __name__,
    {
        "BuiltInEncoding": ".built_in_encoding",
        "Encoding": ".encoding",
        "GlyphList": ".glyph_list",
        "MacExpertEncoding": ".mac_expert_encoding",
        "MacRomanEncoding": ".mac_roman_encoding",
        "StandardEncoding": ".standard_encoding",
        "SymbolEncoding": ".symbol_encoding",
        "WinAnsiEncoding": ".win_ansi_encoding",
        "ZapfDingbatsEncoding": ".zapf_dingbats_encoding",
    },
)

__all__ = [
    "BuiltInEncoding",
    "Encoding",
    "GlyphList",
    "MacExpertEncoding",
    "MacRomanEncoding",
    "StandardEncoding",
    "SymbolEncoding",
    "WinAnsiEncoding",
    "ZapfDingbatsEncoding",
]
