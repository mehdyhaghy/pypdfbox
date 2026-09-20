"""Bidi-aware base class for glyph-layout processors.

Mirrors ``org.apache.pdfbox.pdmodel.AbstractGlyphLayoutProcessor``
(PDFBox 3.0.9-SNAPSHOT,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/AbstractGlyphLayoutProcessor.java``).

Introduced upstream for PDFBOX-4951 (commit "Refactoring, separate Bidi from
showText, introduce glyphLayoutProcessor.getStringWidth"). It factors the
bidirectional splitting / reordering out of the backend implementations so a
backend only has to handle a single unidirectional run at a time.

Upstream uses ``java.text.Bidi``; pypdfbox routes through
:mod:`pypdfbox.text.bidi`, the stdlib-only UAX #9 port already used by
``PDFTextStripper.handle_direction``.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .glyph_layout_processor_interface import GlyphLayoutProcessorInterface

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    from .content_stream_for_glyph_layout_interface import (
        ContentStreamForGlyphLayoutInterface,
    )

__all__ = ["AbstractGlyphLayoutProcessor"]

# ``java.text.Bidi.DIRECTION_LEFT_TO_RIGHT``.
_DIRECTION_LEFT_TO_RIGHT = 0


class AbstractGlyphLayoutProcessor(GlyphLayoutProcessorInterface, ABC):
    """Abstract super class for classes implementing
    :class:`~pypdfbox.pdmodel.glyph_layout_processor_interface.GlyphLayoutProcessorInterface`.

    Mirrors upstream's ``AbstractGlyphLayoutProcessor`` (Java lines 32-179).
    Author: Volker Kunert.
    """

    class TextAndBidiLevel:
        """Class for text and Bidi-Level. Mirrors upstream's
        ``protected static class TextAndBidiLevel`` (Java lines 37-59)."""

        __slots__ = ("_bidi_level", "_text")

        def __init__(self, text: str, bidi_level: int) -> None:
            self._text = text
            self._bidi_level = bidi_level

        def get_text(self) -> str:
            """Mirrors ``getText()`` (Java line 49)."""
            return self._text

        def get_bidi_level(self) -> int:
            """Mirrors ``getBidiLevel()`` (Java line 54)."""
            return self._bidi_level

    @abstractmethod
    def get_string_width_uni(
        self,
        font: PDType0Font,
        font_size: float,
        text: str,
        bidi_level: int,
    ) -> float:
        """Compute the string width for a unidirectional string.

        Mirrors the protected abstract ``getStringWidthUni`` (Java line 69).
        """

    def get_string_width(
        self, font: PDType0Font, font_size: float, text: str
    ) -> float:
        """Compute the width for a text.

        Mirrors ``getStringWidth`` (Java lines 80-89).
        """
        width = 0.0
        for text_and_bidi_level in self.do_bidi_splitting_and_reordering(text):
            width += self.get_string_width_uni(
                font,
                font_size,
                text_and_bidi_level.get_text(),
                text_and_bidi_level.get_bidi_level(),
            )
        return width

    @abstractmethod
    def show_text_uni(
        self,
        content_stream: ContentStreamForGlyphLayoutInterface,
        font: PDType0Font,
        font_size: float,
        text: str,
        bidi_level: int,
    ) -> None:
        """Show unidirectional text using glyph positioning (if needed).

        Mirrors the protected abstract ``showTextUni`` (Java lines 103-104).
        """

    def show_text(
        self,
        content_stream: ContentStreamForGlyphLayoutInterface,
        font: PDType0Font,
        font_size: float,
        text: str,
    ) -> None:
        """Show a text using glyph positioning (if needed).

        Mirrors ``showText`` (Java lines 117-125).
        """
        for text_and_bidi_level in self.do_bidi_splitting_and_reordering(text):
            self.show_text_uni(
                content_stream,
                font,
                font_size,
                text_and_bidi_level.get_text(),
                text_and_bidi_level.get_bidi_level(),
            )

    def do_bidi_splitting_and_reordering(
        self, text: str
    ) -> tuple[AbstractGlyphLayoutProcessor.TextAndBidiLevel, ...]:
        """Do Bidi splitting and reordering.

        Mirrors ``doBidiSplittingAndReordering`` (Java lines 132-178).
        Upstream returns an unmodifiable ``List``; the port returns a tuple
        for the same immutability guarantee.

        Java ``Bidi`` API mapping:

        * ``Bidi.requiresBidi(char[], 0, length)`` →
          :func:`pypdfbox.text.bidi.requires_bidi`
        * ``new Bidi(text, DIRECTION_DEFAULT_LEFT_TO_RIGHT)`` →
          :class:`pypdfbox.text.bidi.BidiResolver` with the P2/P3 base
          direction from :func:`pypdfbox.text.bidi.get_paragraph_direction`
        * ``bidi.isMixed()`` → more than one distinct embedding level, or a
          single run whose direction differs from the base direction
        * ``getRunCount`` / ``getRunLevel`` / ``getRunStart`` /
          ``getRunLimit`` → maximal runs of equal embedding level
        * ``Bidi.reorderVisually(levels, 0, runs, 0, runCount)`` →
          :func:`pypdfbox.text.bidi.reorder_runs_visually`
        """
        # ``pypdfbox.text`` is imported lazily: ``pypdfbox.text.__init__``
        # pulls in the text-extraction stack, which imports ``pdmodel``.
        from pypdfbox.text.bidi import (
            BidiResolver,
            get_paragraph_direction,
            reorder_runs_visually,
            requires_bidi,
        )

        text_and_bidi_levels: list[AbstractGlyphLayoutProcessor.TextAndBidiLevel] = []

        # Objects.requireNonNull(text, "Text must be set")
        if text is None:
            raise TypeError("Text must be set")

        if requires_bidi(text):
            base_level = get_paragraph_direction(text)
            levels = BidiResolver().resolve(text, paragraph_direction=base_level)
            # Maximal runs of equal embedding level, in logical order.
            runs: list[tuple[int, int, int]] = []
            for index, level in enumerate(levels):
                if runs and runs[-1][2] == level:
                    runs[-1] = (runs[-1][0], index + 1, level)
                else:
                    runs.append((index, index + 1, level))
            run_levels = [run[2] for run in runs]
            # ``Bidi.isMixed()``: mixed runs of LTR and RTL text, or the base
            # direction differs from the direction of the only run of text.
            is_mixed = len(set(run_levels)) > 1 or (
                bool(run_levels) and run_levels[0] % 2 != base_level % 2
            )
            if is_mixed:
                # Split and Reorder
                # See PDFTextStripper.handle_direction
                # reorder individual parts based on their levels
                order = reorder_runs_visually(list(range(len(runs))), run_levels)
                for index in order:
                    start, limit, bidi_level = runs[index]
                    part = text[start:limit]
                    text_and_bidi_levels.append(
                        AbstractGlyphLayoutProcessor.TextAndBidiLevel(part, bidi_level)
                    )
            else:
                text_and_bidi_levels.append(
                    AbstractGlyphLayoutProcessor.TextAndBidiLevel(text, base_level)
                )
        else:
            text_and_bidi_levels.append(
                AbstractGlyphLayoutProcessor.TextAndBidiLevel(
                    text, _DIRECTION_LEFT_TO_RIGHT
                )
            )
        return tuple(text_and_bidi_levels)
