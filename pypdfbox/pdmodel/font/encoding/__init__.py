from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .built_in_encoding import BuiltInEncoding
    from .dictionary_encoding import DictionaryEncoding
    from .encoding import Encoding
    from .mac_expert_encoding import MacExpertEncoding
    from .mac_os_roman_encoding import MacOSRomanEncoding
    from .mac_roman_encoding import MacRomanEncoding
    from .standard_encoding import StandardEncoding
    from .symbol_encoding import SymbolEncoding
    from .type1_encoding import Type1Encoding
    from .win_ansi_encoding import WinAnsiEncoding
    from .zapf_dingbats_encoding import ZapfDingbatsEncoding

__getattr__, __dir__ = _attach(
    __name__,
    {
        "BuiltInEncoding": ".built_in_encoding",
        "DictionaryEncoding": ".dictionary_encoding",
        "Encoding": ".encoding",
        "MacExpertEncoding": ".mac_expert_encoding",
        "MacOSRomanEncoding": ".mac_os_roman_encoding",
        "MacRomanEncoding": ".mac_roman_encoding",
        "StandardEncoding": ".standard_encoding",
        "SymbolEncoding": ".symbol_encoding",
        "Type1Encoding": ".type1_encoding",
        "WinAnsiEncoding": ".win_ansi_encoding",
        "ZapfDingbatsEncoding": ".zapf_dingbats_encoding",
    },
)

__all__ = [
    "BuiltInEncoding",
    "DictionaryEncoding",
    "Encoding",
    "MacExpertEncoding",
    "MacOSRomanEncoding",
    "MacRomanEncoding",
    "StandardEncoding",
    "SymbolEncoding",
    "Type1Encoding",
    "WinAnsiEncoding",
    "ZapfDingbatsEncoding",
]
