from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .damaged_font_exception import DamagedFontException
    from .token import (
        Kind,
        Token,
    )
    from .type1_char_string_reader import Type1CharStringReader
    from .type1_font import Type1Font
    from .type1_font_util import Type1FontUtil
    from .type1_mapping import Type1Mapping
    from .type1_parser import (
        Type1Lexer,
        Type1Parser,
    )

__getattr__, __dir__ = _attach(
    __name__,
    {
        "DamagedFontException": ".damaged_font_exception",
        "Kind": ".token",
        "Token": ".token",
        "Type1CharStringReader": ".type1_char_string_reader",
        "Type1Font": ".type1_font",
        "Type1FontUtil": ".type1_font_util",
        "Type1Mapping": ".type1_mapping",
        "Type1Lexer": ".type1_parser",
        "Type1Parser": ".type1_parser",
    },
)

__all__ = [
    "DamagedFontException",
    "Kind",
    "Token",
    "Type1CharStringReader",
    "Type1Font",
    "Type1FontUtil",
    "Type1Lexer",
    "Type1Mapping",
    "Type1Parser",
]
