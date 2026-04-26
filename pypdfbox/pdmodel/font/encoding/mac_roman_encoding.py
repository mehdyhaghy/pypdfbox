from __future__ import annotations

from pypdfbox.fontbox.encoding.mac_roman_encoding import _TABLE

from .encoding import Encoding


class MacRomanEncoding(Encoding):
    """The Mac Roman Encoding.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.MacRomanEncoding``.
    """

    INSTANCE: "MacRomanEncoding"

    def __init__(self) -> None:
        super().__init__()
        for code, name in _TABLE:
            self.add(code, name)

    def get_encoding_name(self) -> str:
        return "MacRomanEncoding"


MacRomanEncoding.INSTANCE = MacRomanEncoding()


__all__ = ["MacRomanEncoding"]
