"""Legacy text-engine subclass used by ``PDFTextStripper``.

Mirrors ``org.apache.pdfbox.text.LegacyPDFStreamEngine`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/text/LegacyPDFStreamEngine.java``).

Upstream marks this class package-private and explicitly states
"DO NOT USE THIS CODE UNLESS YOU ARE WORKING WITH PDFTextStripper. THIS
CODE IS DELIBERATELY INCORRECT". The class exists solely to preserve a
heuristic ``showGlyph`` implementation that ``PDFTextStripper`` historically
depends on.

In pypdfbox, the same heuristics live inside :class:`PDFTextStripper`'s
own ``show_glyph``/``compute_font_height`` to avoid a tangle of mixin
state. This module exposes ``LegacyPDFStreamEngine`` as a thin
``PDFTextStripper`` alias so user code that subclasses
``LegacyPDFStreamEngine`` keeps compiling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine

if TYPE_CHECKING:
    pass


class LegacyPDFStreamEngine(PDFStreamEngine):
    """Legacy heuristics retained for ``PDFTextStripper`` parity.

    The full glyph-positioning logic is hosted in
    :class:`pypdfbox.text.pdf_text_stripper.PDFTextStripper`; the methods
    below mirror upstream's hook surface (``show_glyph``,
    ``compute_font_height``, ``process_text_position``) so that user
    subclasses can intercept the same lifecycle events.
    """

    def __init__(self) -> None:
        super().__init__()
        self._page_rotation: int = 0
        self._page_size = None
        self._translate_matrix = None
        self._font_height_map: dict[int, float] = {}

    def process_page(self, page) -> None:
        """Reset rotation/cropbox bookkeeping and delegate to upstream."""
        self._page_rotation = page.get_rotation()
        self._page_size = page.get_crop_box()
        llx = self._page_size.get_lower_left_x()
        lly = self._page_size.get_lower_left_y()
        if llx == 0 and lly == 0:
            self._translate_matrix = None
        else:
            from pypdfbox.util.matrix import Matrix

            self._translate_matrix = Matrix.get_translate_instance(-llx, -lly)
        super().process_page(page)

    def show_glyph(self, text_rendering_matrix, font, code: int, displacement) -> None:  # type: ignore[override]
        """Subclasses override to receive glyph events; default is a no-op."""
        return None

    def compute_font_height(self, font) -> float:
        """Heuristic font height. Mirrors upstream's ``computeFontHeight``."""
        bbox = font.get_bounding_box()
        if bbox.get_lower_left_y() < -32768:
            bbox.set_lower_left_y(-(bbox.get_lower_left_y() + 65536))
        glyph_height = bbox.get_height() / 2
        font_descriptor = font.get_font_descriptor()
        if font_descriptor is not None:
            cap_height = font_descriptor.get_cap_height()
            if cap_height != 0 and (cap_height < glyph_height or glyph_height == 0):
                glyph_height = cap_height
            ascent = font_descriptor.get_ascent()
            descent = font_descriptor.get_descent()
            if (
                cap_height > ascent
                and ascent > 0
                and descent < 0
                and ((ascent - descent) / 2 < glyph_height or glyph_height == 0)
            ):
                glyph_height = (ascent - descent) / 2
        from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font  # local import

        if isinstance(font, PDType3Font):
            _, height = font.get_font_matrix().transform_point(0, glyph_height)
            return height
        return glyph_height / 1000

    def process_text_position(self, text) -> None:
        """Hook called per glyph; subclasses override to consume."""
        return None


__all__ = ["LegacyPDFStreamEngine"]
