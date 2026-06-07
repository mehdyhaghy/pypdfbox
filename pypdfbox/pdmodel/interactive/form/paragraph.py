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
        ``width``. Mirrors upstream ``getInterWordSpacing`` (Java line
        363): ``(width - lineWidth) / (words.size() - 1)`` with **no**
        guard against a single-word line. Upstream is Java float
        arithmetic, where dividing by zero yields ``Infinity`` /
        ``-Infinity`` (not an exception); we reproduce that so a
        single-word justify line propagates a non-finite value to
        ``new_line_at_offset`` exactly as upstream does (it then raises
        the "not a finite number" guard)."""
        gaps = len(self._words) - 1
        numerator = width - self._line_width
        if gaps == 0:
            # Java float division by zero -> +/-Infinity (or NaN for 0/0).
            if numerator > 0:
                return float("inf")
            if numerator < 0:
                return float("-inf")
            return float("nan")
        return numerator / gaps

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
        ``PlainText.Paragraph.getLines`` lines 160–249). Uses a simple
        whitespace-based break iterator as a stand-in for the upstream
        Java ``BreakIterator.getLineInstance()``; the public contract is
        the same and the force-split fallback (PDFBOX-5049 /
        PDFBOX-6082) for over-wide single words is preserved verbatim so
        that values such as a long unbroken digit run wrap to the same
        line shape Acrobat produces (per the ``testMultilineBreak``
        oracle, PDFBOX-3835).
        """
        if width <= 0:
            return []
        scale = font_size / _FONT_SCALE

        # Materialise the segment list so we can splice into it when a
        # single segment needs to be force-split (PDFBOX-5049).
        # Each segment is a "word + trailing whitespace" or pure
        # whitespace run, matching upstream's BreakIterator semantics
        # for plain ASCII text.
        segments = _BREAK.findall(self._text_content)
        line_width = 0.0
        text_lines: list[Line] = []
        text_line = Line()

        i = 0
        while i < len(segments):
            word_text = segments[i]
            word_width = font.get_string_width(word_text) * scale

            line_width = line_width + word_width

            # If the trailing whitespace pushed us over, subtract it
            # back (upstream lines 188–193).
            if (
                line_width >= width
                and word_text
                and word_text[-1].isspace()
            ):
                ws_width = font.get_string_width(word_text[-1]) * scale
                line_width = line_width - ws_width

            # Close out the current line if appending this word would
            # overflow and we already have at least one word on it
            # (upstream lines 195–201).
            if line_width >= width and text_line.get_words():
                text_line.set_width(text_line.calculate_width(font, font_size))
                text_lines.append(text_line)
                text_line = Line()
                line_width = font.get_string_width(word_text) * scale

            # Force-split a single oversized word so that at least one
            # character is placed on this line (PDFBOX-5049 /
            # PDFBOX-6082, upstream lines 203–228).
            word_needs_split = False
            split_offset = len(word_text)
            if (
                len(word_text) > 1
                and word_width > width
                and not text_line.get_words()
            ):
                word_needs_split = True
                prefix_width = Paragraph.build_prefix_widths(
                    word_text, font, scale
                )
                split_offset = Paragraph.find_max_fitting_chars(
                    prefix_width, width
                )
                word_text = word_text[:split_offset]
                word_width = prefix_width[split_offset]
                line_width = word_width

            word_instance = Word(word_text)
            word_instance.set_attributes({"WIDTH": word_width})
            text_line.add_word(word_instance)

            if word_needs_split:
                # Replace the current segment with its un-emitted tail
                # and re-enter the loop on the same index — upstream's
                # iterator advance is suppressed in this branch
                # (upstream lines 236–244).
                remainder = segments[i][split_offset:]
                if remainder:
                    segments[i] = remainder
                else:  # pragma: no cover - unreachable in valid input
                    # find_max_fitting_chars caps at the largest k with
                    # prefix_width[k] < width; since we entered the
                    # split branch with word_width > width, k is always
                    # < len(word_text) so the remainder slice has at
                    # least one char. Kept as a defensive arm mirroring
                    # upstream's iterator-advance shape.
                    i += 1
            else:
                i += 1

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
