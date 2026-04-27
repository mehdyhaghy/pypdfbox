from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.text.text_position import TextPosition


class WordWithTextPositions:
    """A normalized word plus the :class:`TextPosition` list that produced it.

    Mirrors the upstream private inner class
    ``org.apache.pdfbox.text.PDFTextStripper.WordWithTextPositions``:

        private static final class WordWithTextPositions {
            final String text;
            final List<TextPosition> textPositions;
            ...
            public String getText()                       { return text; }
            public List<TextPosition> getTextPositions()  { return textPositions; }
        }

    Note that the number of entries in ``text_positions`` may differ
    from the number of characters in ``text`` due to Unicode
    normalization of the decoded glyph stream.

    Promoted from a private inner class to a top-level public type so
    callers (e.g. region-based extraction, custom downstream layout
    pipelines) can consume the structure directly.
    """

    def __init__(self, word: str, positions: list[TextPosition]) -> None:
        self.text: str = word
        self.text_positions: list[TextPosition] = positions

    def get_text(self) -> str:
        return self.text

    def get_text_positions(self) -> list[TextPosition]:
        return self.text_positions


__all__ = ["WordWithTextPositions"]
