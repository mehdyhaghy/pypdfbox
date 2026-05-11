from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .word import Word

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font import PDFont


_FONT_SCALE = 1000.0

# Whitespace break positions (after each whitespace). Python's stdlib
# does not ship a ``BreakIterator`` equivalent, so the lite port uses
# the same heuristic upstream's BreakIterator falls back to for plain
# ASCII text: split on whitespace boundaries, preserving the trailing
# whitespace on each segment.
_BREAK = re.compile(r"\S+\s*|\s+")


class Line:
    """An individual line of text. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.PlainText.Line``
    (upstream lines 323–372)."""

    def __init__(self) -> None:
        self._words: list[Word] = []
        self._line_width: float = 0.0

    def get_width(self) -> float:
        return self._line_width

    def set_width(self, width: float) -> None:
        self._line_width = width

    def get_words(self) -> list[Word]:
        return self._words

    def add_word(self, word: Word) -> None:
        self._words.append(word)

    def get_inter_word_spacing(self, width: float) -> float:
        """Return the per-gap spacing needed to justify this line to
        ``width``. Caller is responsible for ensuring
        ``len(words) > 1`` — upstream divides by ``words.size() - 1``
        without a guard."""
        return (width - self._line_width) / (len(self._words) - 1)

    def calculate_width(self, font: PDFont, font_size: float) -> float:
        """Return the rendered width of this line, accounting for the
        Acrobat convention of dropping the trailing whitespace on the
        last word. Mirrors upstream ``calculateWidth``
        (lines 338–356)."""
        scale = font_size / _FONT_SCALE
        calculated_width = 0.0
        last_index = len(self._words) - 1
        for index, word in enumerate(self._words):
            attrs = word.get_attributes() or {}
            calculated_width += float(attrs.get("WIDTH", 0.0))
            text = word.get_text()
            if (
                index == last_index
                and text
                and text[-1].isspace()
            ):
                calculated_width -= font.get_string_width(text[-1]) * scale
        return calculated_width


class Paragraph:
    """A block of text to be formatted as a whole. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.PlainText.Paragraph``
    (upstream lines 134–318)."""

    def __init__(self, text: str) -> None:
        self._text_content: str = text

    def get_text(self) -> str:
        return self._text_content

    def get_lines(
        self, font: PDFont, font_size: float, width: float
    ) -> list[Line]:
        """Break the paragraph into individual lines fitting ``width``.

        Returns an empty list when ``width <= 0`` (mirrors upstream
        line 164–167). Uses a simple whitespace-based break iterator;
        the upstream algorithm is more sophisticated (full ICU-style
        ``BreakIterator``) but the public contract is the same: each
        line carries one or more :class:`Word` instances with a
        pre-computed scaled width attribute.
        """
        if width <= 0:
            return []
        scale = font_size / _FONT_SCALE

        line_width = 0.0
        text_lines: list[Line] = []
        text_line = Line()

        for word_text in _BREAK.findall(self._text_content):
            word_width = font.get_string_width(word_text) * scale
            line_width += word_width

            # if trailing whitespace pushed us over, subtract it back
            if line_width >= width and word_text and word_text[-1].isspace():
                ws_width = font.get_string_width(word_text[-1]) * scale
                line_width -= ws_width

            if line_width >= width and text_line.get_words():
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

    @staticmethod
    def build_prefix_widths(
        word: str, font: PDFont, scale: float
    ) -> list[float]:
        """Build a prefix-sum array of scaled character widths for
        ``word``. Mirrors upstream
        ``PlainText.Paragraph.buildPrefixWidths`` (lines 262–282).

        ``scale`` is ``font_size / 1000`` precomputed by the caller.
        Returns a ``[len(word) + 1]`` array whose ``k``-th entry is the
        cumulative width of ``word[:k]``.
        """
        word_len = len(word)
        prefix_width = [0.0] * (word_len + 1)
        i = 0
        while i < word_len:
            # Python strings are already code-point aware; count one
            # code point at a time so surrogate pairs are handled
            # transparently by the iteration.
            code_point = word[i]
            cp_width = font.get_string_width(code_point) * scale
            prefix_width[i + 1] = prefix_width[i] + cp_width
            i += 1
        return prefix_width

    @staticmethod
    def find_max_fitting_chars(
        prefix_width: list[float], width: float
    ) -> int:
        """Binary-search the largest ``k >= 1`` such that
        ``prefix_width[k] < width``. Mirrors upstream
        ``PlainText.Paragraph.findMaxFittingChars`` (lines 300–317).

        Returns ``1`` if even a single char overflows (PDFBOX-6082).
        """
        lo = 1
        hi = len(prefix_width) - 1
        while lo < hi:
            mid = (lo + hi + 1) >> 1
            if prefix_width[mid] < width:
                lo = mid
            else:
                hi = mid - 1
        return lo


__all__ = ["Line", "Paragraph"]
