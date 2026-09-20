"""Content-stream surface a glyph-layout processor writes through.

Mirrors ``org.apache.pdfbox.pdmodel.ContentStreamForGlyphLayoutInterface``
(PDFBox 3.0.9-SNAPSHOT,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/ContentStreamForGlyphLayoutInterface.java``).

Introduced upstream for PDFBOX-4951. Implemented by the content-stream
writers so a
:class:`~pypdfbox.pdmodel.glyph_layout_processor_interface.GlyphLayoutProcessorInterface`
implementation can emit positioned glyphs without depending on a concrete
writer class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .glyphs_and_positions import GlyphsAndPositions

__all__ = ["ContentStreamForGlyphLayoutInterface"]


class ContentStreamForGlyphLayoutInterface(ABC):
    """Mirrors upstream's ``ContentStreamForGlyphLayoutInterface``
    (Java lines 21-49)."""

    @abstractmethod
    def show_glyphs_with_positioning(
        self, glyphs_and_positions: GlyphsAndPositions
    ) -> None:
        """Show the given glyphs at the specified positions.

        Mirrors ``showGlyphsWithPositioning(GlyphsAndPositions)``
        (Java line 30).
        """

    @abstractmethod
    def show_glyph_codes(self, glyph_codes: Sequence[int]) -> None:
        """Show the glyphs for the given glyph codes.

        Mirrors ``showGlyphCodes(int[])`` (Java line 38).
        """

    @abstractmethod
    def set_text_rise(self, rise: float) -> None:
        """Set the text rise value, i.e. move the baseline up or down.

        Mirrors ``setTextRise(float)`` (Java line 48).
        """
