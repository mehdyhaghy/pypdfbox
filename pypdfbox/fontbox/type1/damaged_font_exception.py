"""Port of ``org.apache.fontbox.type1.DamagedFontException``."""

from __future__ import annotations


class DamagedFontException(OSError):
    """Thrown when a font is damaged and cannot be read.

    Mirrors upstream ``DamagedFontException extends IOException``
    (fontbox ``type1/DamagedFontException.java``). ``IOException`` maps to
    Python's :class:`OSError` per repo convention, matching the other
    Type1 lexer/parser I/O failures which also raise :class:`OSError`.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
