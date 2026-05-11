"""Marker holding a ``TextPosition`` or a "word break" sentinel.

Mirrors the private inner class ``PDFTextStripper.LineItem`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/text/PDFTextStripper.java`` lines
2133-2163).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from pypdfbox.text.text_position import TextPosition


class LineItem:
    """A ``TextPosition`` slot inside a line buffer.

    The singleton :attr:`WORD_SEPARATOR` represents an inferred whitespace
    break between two adjacent glyph runs.
    """

    WORD_SEPARATOR: ClassVar[LineItem]

    def __init__(self, text_position: TextPosition | None = None) -> None:
        self._text_position = text_position

    @classmethod
    def get_word_separator(cls) -> LineItem:
        """Return the shared word-break sentinel."""
        return cls.WORD_SEPARATOR

    def get_text_position(self) -> TextPosition | None:
        return self._text_position

    def is_word_separator(self) -> bool:
        return self._text_position is None


LineItem.WORD_SEPARATOR = LineItem()

__all__ = ["LineItem"]
