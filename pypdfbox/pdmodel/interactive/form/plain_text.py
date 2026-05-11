from __future__ import annotations

import re

from .paragraph import Line, Paragraph
from .word import Word

# Match Java's ``\R`` linebreak meta-character (any Unicode linebreak):
#   CRLF | LF | VT | FF | CR | NEL | LS | PS
_LINEBREAK = re.compile(
    "\r\n|[\n\r  ]"
)


class PlainText:
    """A block of text. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.PlainText``
    (upstream lines 37–87).

    A block of text can contain multiple paragraphs which are treated
    individually within the block placement. Construct from a single
    string (split on Unicode line breaks) or from a list of strings
    (one paragraph per entry).
    """

    _FONT_SCALE: float = 1000.0

    def __init__(self, text_value: str | list[str]) -> None:
        if isinstance(text_value, list):
            self._paragraphs = [Paragraph(part) for part in text_value]
            return

        if text_value == "":
            self._paragraphs = [Paragraph("")]
            return

        # Replace tabs with spaces, then split on Unicode line breaks
        normalised = text_value.replace("\t", " ")
        parts = _LINEBREAK.split(normalised)
        self._paragraphs = []
        for part in parts:
            # Acrobat prints a space for an empty paragraph
            self._paragraphs.append(Paragraph(part if part else " "))

    def get_paragraphs(self) -> list[Paragraph]:
        return self._paragraphs


# Re-export the inner classes so they can be imported through this
# module the same way upstream callers access
# ``PlainText.Paragraph`` / ``PlainText.Line`` / ``PlainText.Word``.
PlainText.Paragraph = Paragraph  # type: ignore[attr-defined]
PlainText.Line = Line  # type: ignore[attr-defined]
PlainText.Word = Word  # type: ignore[attr-defined]


__all__ = ["PlainText"]
