"""Pluggable glyph-layout (text shaping) backend interface.

Mirrors ``org.apache.pdfbox.pdmodel.GlyphLayoutProcessorInterface``
(PDFBox 3.0.9-SNAPSHOT,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/GlyphLayoutProcessorInterface.java``).

Introduced upstream for PDFBOX-4951 ("Sequences of DIN 91379 with combining
letters are rendered incorrectly"). Upstream ships **no** implementation in
the core ``pdfbox`` artifact — the shaping backends live in the separate
optional ``pdfbox-layout-fop`` / ``pdfbox-layout-awt`` Maven modules. pypdfbox
follows that split: this package contains the interface and the wiring only,
and everything keeps working with no processor registered.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font.pd_font import PDFont
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    from .content_stream_for_glyph_layout_interface import (
        ContentStreamForGlyphLayoutInterface,
    )

__all__ = ["GlyphLayoutProcessorInterface"]


class GlyphLayoutProcessorInterface(ABC):
    """Interface for glyph layout that is independent of a specific
    implementation so that more implementations can be tried in the future.

    Mirrors upstream's ``GlyphLayoutProcessorInterface`` (Java lines 27-62).
    Author: Volker Kunert.
    """

    @abstractmethod
    def supports_font(self, font: PDFont) -> bool:
        """``True`` if glyph layout is supported for this font and this font
        is a ``PDType0Font``.

        Mirrors ``supportsFont(PDFont)`` (Java line 39).
        """

    @abstractmethod
    def get_string_width(
        self, font: PDType0Font, font_size: float, text: str
    ) -> float:
        """Compute the width for a text.

        Mirrors ``getStringWidth(PDType0Font, float, String)``
        (Java line 48).
        """

    @abstractmethod
    def show_text(
        self,
        content_stream: ContentStreamForGlyphLayoutInterface,
        font: PDType0Font,
        font_size: float,
        text: str,
    ) -> None:
        """Show a text using glyph positioning (if needed).

        Mirrors ``showText(ContentStreamForGlyphLayoutInterface,
        PDType0Font, float, String)`` (Java line 61).
        """
