"""Encoding pane for simple fonts.

Ported from ``org.apache.pdfbox.debugger.fontencodingpane.SimpleFont``.

Renders the 256 single-byte codepoints of a Type1 / TrueType /
MMType1 font as ``(code, glyph name, unicode, glyph)`` rows.
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any

from pypdfbox.debugger.fontencodingpane.font_encoding_view import FontEncodingView
from pypdfbox.debugger.fontencodingpane.font_pane import FontPane

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font import PDSimpleFont

_LOG = logging.getLogger(__name__)

NO_GLYPH: str = "None"


class SimpleFont(FontPane):
    """Glyph table + Unicode breakdown for a :class:`PDSimpleFont`.

    Mirrors upstream ``SimpleFont`` (package-private). Constructor walks
    codes 0..255, calls ``font.to_unicode(code)`` + ``font.get_encoding().get_name(code)``
    to compute the row, and stores the glyph outline (``get_path``) for
    the view to render.
    """

    def __init__(self, font: PDSimpleFont, master: tk.Misc | None = None) -> None:
        """Build the pane.

        :param font: a :class:`PDSimpleFont` — Type 1, TrueType, or
            MMType1. Type 3 is handled by :class:`Type3Font`.
        :param master: parent Tk widget for the view.
        :raises OSError: when reading the embedded font program fails;
            mirrors upstream's ``throws IOException``.
        """
        self._font = font
        self._total_available_glyphs = 0

        table_data = self.get_glyphs(font)
        y_bounds = self.get_y_bounds(table_data, 3)

        attributes: dict[str, str] = {
            "Font": str(font.get_name()),
            "Encoding": self.get_encoding_name(font),
            "Glyphs": str(self._total_available_glyphs),
            "Standard 14": str(bool(font.is_standard14())),
            "Embedded": str(bool(font.is_embedded())),
        }

        self._view = FontEncodingView(
            master,
            table_data,
            attributes,
            ["Code", "Glyph Name", "Unicode Character", "Glyph"],
            y_bounds,
        )

    # ---- FontPane ----------------------------------------------------------

    def get_panel(self) -> tk.Misc:
        return self._view.get_panel()

    @property
    def view(self) -> FontEncodingView:
        """The underlying :class:`FontEncodingView` (testing hook)."""
        return self._view

    @property
    def total_available_glyphs(self) -> int:
        """Number of codes that resolved to an actual glyph."""
        return self._total_available_glyphs

    # ---- helpers -----------------------------------------------------------

    def get_glyphs(self, font: PDSimpleFont) -> list[list[Any]]:
        """Build the ``Object[256][4]`` table upstream's ``getGlyphs``
        constructs. Each row is ``[code, glyph_name, unicode, glyph_path]``.

        Mirrors upstream ``SimpleFont.getGlyphs(PDSimpleFont)`` (package-
        private). Promoted to a public method here so parity tooling
        recognises it; the underscore-prefixed name is retained as a
        back-compat alias.
        """
        rows: list[list[Any]] = []
        encoding = font.get_encoding_typed()
        for code in range(256):
            unicode_char: str | None = None
            try:
                unicode_char = font.to_unicode(code)
            except OSError:
                unicode_char = None
            if unicode_char is None:
                # Mirrors PDSimpleFont fallback in LegacyPDFStreamEngine —
                # treat the code byte as a Latin-1 codepoint.
                unicode_char = chr(code)

            in_encoding = encoding is not None and encoding.contains(code)
            if in_encoding or unicode_char is not None:
                glyph_name = (
                    encoding.get_name(code) if encoding is not None else ".notdef"
                )
                glyph_path: Any
                try:
                    # Upstream uses ``font.getPath(int)`` from PDVectorFont;
                    # ``PDSimpleFont.get_path`` takes a glyph name, so use
                    # the name route. (Upstream notes the PDFBOX-3445
                    # workaround that prefers the code-based lookup, but
                    # the name lookup is what the pypdfbox API exposes.)
                    glyph_path = font.get_path(glyph_name)
                except OSError as exc:
                    _LOG.error(
                        "Couldn't render code %d ('%s') of font %s: %s",
                        code,
                        glyph_name,
                        font.get_name(),
                        exc,
                    )
                    glyph_path = []
                rows.append([code, glyph_name, unicode_char, glyph_path])
                self._total_available_glyphs += 1
            else:
                # No encoding entry for ``code`` — show ``.notdef``.
                try:
                    notdef = font.get_path(".notdef")
                except OSError:
                    notdef = []
                rows.append([code, NO_GLYPH, NO_GLYPH, notdef])
        return rows

    # Back-compat private alias (was the original name before parity promotion).
    _get_glyphs = get_glyphs

    @staticmethod
    def get_encoding_name(font: PDSimpleFont) -> str:
        """Return a human-readable encoding identifier for ``font``.

        Mirrors upstream ``SimpleFont.getEncodingName(PDSimpleFont)``.
        """
        encoding = font.get_encoding_typed()
        if encoding is None:
            return "(null)"
        name = encoding.get_encoding_name() or type(encoding).__name__
        return f"{type(font).__name__} / {name}"
