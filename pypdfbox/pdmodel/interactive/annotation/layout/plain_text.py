from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pypdfbox.pdmodel.interactive.form.paragraph import Line
from pypdfbox.pdmodel.interactive.form.word import Word

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font import PDFont

# Match Java's ``\R`` linebreak meta-character (any Unicode linebreak):
#   CRLF | LF | VT | FF | CR | NEL | LS | PS
_LINEBREAK = re.compile("\r\n|[\n\x0b\x0c\r\x85  ]")

_FONT_SCALE = 1000.0


def _java_split_linebreaks(text: str) -> list[str]:
    """Split ``text`` on Unicode line breaks with Java ``String.split``
    semantics (default limit 0): interior empty fields are kept but
    **trailing** empty fields are removed.

    Two Java edge cases are reproduced exactly:

    * When the pattern does not match at all, Java returns the whole input
      as a single element — so ``"".split("\\R")`` yields ``[""]`` (not
      ``[]``). Python's ``re.split`` also returns ``[""]`` here, and the
      trailing-empty trim must NOT collapse it.
    * A string that is only line break(s), e.g. ``"\n"``, yields ``[]``
      (the lone trailing empties are all removed).
    """
    if _LINEBREAK.search(text) is None:
        # No delimiter present — Java returns the input unchanged.
        return [text]
    parts = _LINEBREAK.split(text)
    while parts and parts[-1] == "":
        parts.pop()
    return parts


class PlainText:
    """A block of text. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.layout.PlainText``
    (upstream lines 37–87).

    This is the *annotation-layout* variant used by the FreeText
    appearance handler — distinct from
    :class:`pypdfbox.pdmodel.interactive.form.plain_text.PlainText`
    (the AcroForm variant). The two upstream classes differ in two
    behaviours that matter for op-sequence parity:

    * **Empty-string constructor.** The layout variant has no special
      empty-string branch: ``"".split("\\R")`` yields ``[""]``, and the
      per-part loop replaces the empty part with a single space ("Acrobat
      prints a space for an empty paragraph"). The form variant instead
      adds ``Paragraph("")``.
    * **Line breaking** (see :class:`Paragraph`): the layout variant has
      no PDFBOX-5049/6082 force-split for over-wide single words and uses
      an unguarded ``line_width >= width`` line-close test.
    """

    def __init__(self, text_value: str | list[str]) -> None:
        if isinstance(text_value, list):
            self._paragraphs = [Paragraph(part) for part in text_value]
            return

        # Replace tabs with spaces, then split on Unicode line breaks
        # with Java ``split`` semantics (trailing empties dropped).
        normalised = text_value.replace("\t", " ")
        parts = _java_split_linebreaks(normalised)
        self._paragraphs = []
        for part in parts:
            # Acrobat prints a space for an empty paragraph
            self._paragraphs.append(Paragraph(part if part else " "))

    def get_paragraphs(self) -> list[Paragraph]:
        return self._paragraphs


class Paragraph:
    """A block of text to be formatted as a whole. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.layout.PlainText.Paragraph``
    (upstream lines 134–206).

    The annotation-layout line breaker differs from the AcroForm one: it
    has **no** force-split for over-wide single words (PDFBOX-5049/6082 is
    AcroForm-only) and its line-close test is the unguarded
    ``line_width >= width`` (an over-wide word therefore lands on its own
    line after an empty preceding line, instead of being char-split)."""

    def __init__(self, text: str) -> None:
        self._text_content: str = text

    def get_text(self) -> str:
        return self._text_content

    def get_lines(
        self, font: PDFont, font_size: float, width: float
    ) -> list[Line]:
        """Break the paragraph into individual lines fitting ``width``.

        Returns an empty list when ``width <= 0``. Mirrors upstream
        ``PlainText.Paragraph.getLines`` (annotation.layout, lines
        154–205). Uses the same whitespace break-iterator stand-in as the
        AcroForm variant (Python ships no ``BreakIterator``), preserving
        trailing whitespace on each segment.
        """
        if width <= 0:
            return []
        scale = font_size / _FONT_SCALE

        segments = _BREAK.findall(self._text_content)
        line_width = 0.0
        text_lines: list[Line] = []
        text_line = Line()

        for word_text in segments:
            word_width = font.get_string_width(word_text) * scale
            line_width = line_width + word_width

            # check if the last word would fit without the whitespace
            # ending it (upstream lines 179–184).
            if (
                line_width >= width
                and word_text
                and word_text[-1].isspace()
            ):
                ws_width = font.get_string_width(word_text[-1]) * scale
                line_width = line_width - ws_width

            # Close the current line whenever the width is exceeded — note
            # there is NO ``and not text_line.get_words()`` guard here, so
            # an over-wide first word closes an empty line then lands alone
            # on the next (upstream lines 186–192).
            if line_width >= width:
                text_line.set_width(text_line.calculate_width(font, font_size))
                text_lines.append(text_line)
                text_line = Line()
                line_width = font.get_string_width(word_text) * scale

            word_instance = Word(word_text)
            word_instance.set_attributes({"WIDTH": word_width})
            text_line.add_word(word_instance)

        text_line.set_width(text_line.calculate_width(font, font_size))
        text_lines.append(text_line)
        return text_lines


# Whitespace break positions — shared heuristic with the AcroForm
# Paragraph: split on whitespace boundaries preserving trailing
# whitespace on each segment (Python ships no ``BreakIterator``).
_BREAK = re.compile(r"\S+\s*|\s+")


# Re-export the inner classes so callers can access them the same way
# upstream does (``PlainText.Paragraph`` / ``PlainText.Line`` /
# ``PlainText.Word``).
PlainText.Paragraph = Paragraph  # type: ignore[attr-defined]
PlainText.Line = Line  # type: ignore[attr-defined]
PlainText.Word = Word  # type: ignore[attr-defined]


__all__ = ["Paragraph", "PlainText"]
