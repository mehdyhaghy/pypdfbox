"""Encoding pane for Type 3 fonts.

Ported from ``org.apache.pdfbox.debugger.fontencodingpane.Type3Font``.

The Swing original renders each Type3 glyph by spinning up a fresh
``PDDocument`` with a one-page content stream that shows the glyph,
then rasterising via ``PDFRenderer``. That round-trip is too expensive
(and brittle) for the debugger port; pypdfbox instead substitutes a
text label of the glyph name into a Pillow image so the table still
distinguishes filled vs. empty rows. The :class:`FontEncodingView`
already handles ``PIL.Image`` instances natively, so the rest of the
pipeline is unchanged.
"""

from __future__ import annotations

import contextlib
import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any

from pypdfbox.debugger.fontencodingpane.font_encoding_view import FontEncodingView
from pypdfbox.debugger.fontencodingpane.font_pane import FontPane
from pypdfbox.debugger.fontencodingpane.simple_font import SimpleFont
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font import PDType3Font
    from pypdfbox.pdmodel.pd_resources import PDResources

_LOG = logging.getLogger(__name__)

NO_GLYPH: str = "No glyph"


class Type3Font(FontPane):
    """Glyph table for a Type 3 font."""

    def __init__(
        self,
        font: PDType3Font,
        resources: PDResources | None,
        master: tk.Misc | None = None,
    ) -> None:
        """Build the pane.

        :param font: the :class:`PDType3Font` to inspect.
        :param resources: the enclosing ``/Resources`` dict — required by
            upstream for the inner rendering pass; kept for parity even
            though pypdfbox's text-only fallback never consults it.
        :param master: parent Tk widget.
        """
        self._font = font
        self._resources = resources
        self._total_available_glyphs = 0
        self._font_bbox: PDRectangle = self._calc_bbox(font)

        table_data = self._get_glyphs(font)

        name = font.get_name()
        descriptor = font.get_font_descriptor()
        if name is None and descriptor is not None:
            name = descriptor.get_font_name()

        attributes: dict[str, str] = {
            "Font": str(name),
            "Encoding": SimpleFont.get_encoding_name(font),
            "Glyphs": str(self._total_available_glyphs),
        }

        self._view = FontEncodingView(
            master,
            table_data,
            attributes,
            ["Code", "Glyph Name", "Unicode Character", "Glyph"],
            None,
        )

    # ---- FontPane ----------------------------------------------------------

    def get_panel(self) -> tk.Misc:
        return self._view.get_panel()

    @property
    def view(self) -> FontEncodingView:
        return self._view

    @property
    def total_available_glyphs(self) -> int:
        return self._total_available_glyphs

    @property
    def font_bbox(self) -> PDRectangle:
        return self._font_bbox

    # ---- helpers -----------------------------------------------------------

    def _calc_bbox(self, font: PDType3Font) -> PDRectangle:
        """Mirror upstream ``calcBBox``: take the union of per-CharProc
        glyph BBoxes, falling back to the font's overall BBox when the
        per-glyph union is empty (PDF.js issue 10717).
        """
        min_x = 0.0
        max_x = 0.0
        min_y = 0.0
        max_y = 0.0
        for index in range(256):
            try:
                char_proc = font.get_char_proc(index)
            except OSError:
                continue
            if char_proc is None:
                continue
            try:
                glyph_bbox = char_proc.get_glyph_bbox()
            except (AttributeError, OSError):
                glyph_bbox = None
            if glyph_bbox is None:
                continue
            min_x = min(min_x, glyph_bbox.get_lower_left_x())
            max_x = max(max_x, glyph_bbox.get_upper_right_x())
            min_y = min(min_y, glyph_bbox.get_lower_left_y())
            max_y = max(max_y, glyph_bbox.get_upper_right_y())

        bbox = PDRectangle(
            float(min_x), float(min_y), float(max_x - min_x), float(max_y - min_y)
        )
        if bbox.get_width() <= 0 or bbox.get_height() <= 0:
            # Less reliable, but good fallback (PDF.js issue 10717).
            fallback = font.get_bounding_box()
            if fallback is not None:
                bbox = PDRectangle(
                    fallback.get_lower_left_x(),
                    fallback.get_lower_left_y(),
                    fallback.get_width(),
                    fallback.get_height(),
                )
        return bbox

    def _get_glyphs(self, font: PDType3Font) -> list[list[Any]]:
        """Mirror upstream ``getGlyphs``: walk codes 0..255, populate a
        4-column row per code, dedupe rendered images on glyph name.
        """
        is_empty = (
            self._font_bbox.get_width() <= 0 or self._font_bbox.get_height() <= 0
        )
        rows: list[list[Any]] = []
        image_cache: dict[str, Any] = {}
        encoding = font.get_encoding_typed()

        for code in range(256):
            try:
                unicode_char = font.to_unicode(code)
            except OSError:
                unicode_char = None
            in_encoding = encoding is not None and encoding.contains(code)
            if in_encoding or unicode_char is not None:
                glyph_name = (
                    encoding.get_name(code) if encoding is not None else ".notdef"
                )
                if is_empty:
                    glyph_value: Any = NO_GLYPH
                elif glyph_name in image_cache:
                    glyph_value = image_cache[glyph_name]
                else:
                    glyph_value = _render_type3_glyph_label(glyph_name)
                    image_cache[glyph_name] = glyph_value
                rows.append([code, glyph_name, unicode_char, glyph_value])
                self._total_available_glyphs += 1
            else:
                rows.append([code, NO_GLYPH, NO_GLYPH, NO_GLYPH])
        return rows


def _render_type3_glyph_label(name: str) -> Any:
    """Render the glyph *name* as small Pillow image.

    Upstream rasterises the actual Type3 content stream via PDFRenderer.
    pypdfbox falls back to a text-label thumbnail so the row is still
    visibly distinct from ``"No glyph"`` rows. Returns ``NO_GLYPH``
    when Pillow is unavailable so the caller still has a sentinel to
    show.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:  # pragma: no cover
        return NO_GLYPH
    img = Image.new("RGB", (40, 40), "white")
    draw = ImageDraw.Draw(img)
    # Truncate the displayed name to fit a 40px-wide cell.
    display = name[:4] if len(name) > 4 else name
    # Pillow's default font subsystem may be unavailable on stripped
    # installs (no default bitmap). In that case leave the image blank
    # rather than failing the build.
    with contextlib.suppress(Exception):
        draw.text((2, 12), display, fill="black")
    return img
