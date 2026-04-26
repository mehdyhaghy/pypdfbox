from __future__ import annotations

import logging

from pypdfbox.cos import COSDictionary
from pypdfbox.fontbox.ttf import TrueTypeFont

from .pd_simple_font import PDSimpleFont

_LOG = logging.getLogger(__name__)


class PDTrueTypeFont(PDSimpleFont):
    """PDF TrueType font. Mirrors PDFBox ``PDTrueTypeFont``."""

    SUB_TYPE = "TrueType"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        # Lazily-loaded embedded TTF — None means "not yet attempted",
        # ``False`` means "tried, no /FontFile2 or parse failed".
        self._ttf: TrueTypeFont | None | bool = None
        self._cmap_subtable = None
        self._cmap_resolved: bool = False

    # ---------- TTF program access ----------

    def _get_true_type_font(self) -> TrueTypeFont | None:
        """Return the parsed TTF for this font's ``/FontFile2`` stream,
        or ``None`` if the font is not embedded or the stream cannot be
        parsed. Result is cached."""
        if self._ttf is not None:
            return self._ttf if isinstance(self._ttf, TrueTypeFont) else None

        descriptor = self.get_font_descriptor()
        if descriptor is None:
            self._ttf = False
            return None
        font_file2 = descriptor.get_font_file2()
        if font_file2 is None:
            self._ttf = False
            return None
        try:
            raw = font_file2.to_byte_array()
            self._ttf = TrueTypeFont.from_bytes(raw)
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to parse /FontFile2 for %s", self.get_name())
            self._ttf = False
            return None
        return self._ttf

    def set_true_type_font(self, ttf: TrueTypeFont | None) -> None:
        """Inject a pre-parsed :class:`TrueTypeFont`. Used by callers
        that already have the font program in hand (avoids a redundant
        re-parse) and by tests that bypass ``/FontFile2``."""
        self._ttf = ttf if ttf is not None else False

    # ---------- glyph widths ----------

    def get_glyph_width(self, code: int) -> float:
        """Advance width for a single character ``code``, in 1/1000 em.

        Resolution order matches PDF 32000-1 §9.7.3 — the font dict's
        ``/Widths`` array (with ``/FirstChar``) takes precedence over
        the embedded font program. Falls back to the ``hmtx`` advance
        from the embedded TrueType, scaled by ``1000 / unitsPerEm``.
        Returns 0.0 when neither source can answer.
        """
        first_char = self.get_first_char()
        widths = self.get_widths()
        if first_char >= 0 and widths:
            idx = code - first_char
            if 0 <= idx < len(widths):
                return float(widths[idx])

        ttf = self._get_true_type_font()
        if ttf is None:
            return 0.0

        gid = self._code_to_gid(code, ttf)
        units_per_em = ttf.get_units_per_em()
        if units_per_em <= 0:
            return 0.0
        advance = ttf.get_advance_width(gid)
        return advance * 1000.0 / units_per_em

    # ---------- code -> glyph_id ----------

    def _code_to_gid(self, code: int, ttf: TrueTypeFont) -> int:
        """Resolve a one-byte character code to a TrueType glyph ID via
        the font's ``/Encoding`` and the embedded ``cmap``.

        Symbolic / no-Encoding fonts: treat ``code`` as the cmap key
        directly (matches the PDFBox behaviour for fonts without a
        meaningful PostScript encoding)."""
        encoding = self.get_encoding_typed()
        cmap = self._get_unicode_cmap(ttf)
        if encoding is not None and cmap is not None:
            from pypdfbox.fontbox.encoding.glyph_list import GlyphList  # noqa: PLC0415

            name = encoding.get_name(code)
            if name and name != ".notdef":
                unicode = GlyphList.DEFAULT.to_unicode(name)
                if unicode:
                    gid = cmap.get_glyph_id(ord(unicode[0]))
                    if gid != 0:
                        return gid
        # Fallback: ask the cmap directly (symbolic fonts / no encoding).
        if cmap is not None:
            return cmap.get_glyph_id(code)
        return 0

    def _get_unicode_cmap(self, ttf: TrueTypeFont):  # type: ignore[no-untyped-def]
        if not self._cmap_resolved:
            try:
                self._cmap_subtable = ttf.get_unicode_cmap_subtable()
            except Exception:  # noqa: BLE001
                _LOG.exception("failed to parse cmap for %s", self.get_name())
                self._cmap_subtable = None
            self._cmap_resolved = True
        return self._cmap_subtable


__all__ = ["PDTrueTypeFont"]
