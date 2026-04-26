from __future__ import annotations

import logging

from pypdfbox.cos import COSDictionary
from pypdfbox.fontbox.cff.cff_font import CFFFont

from .pd_type1_font import PDType1Font

_LOG = logging.getLogger(__name__)


class PDType1CFont(PDType1Font):
    """Type 1 font whose glyph program is a CFF (Compact Font Format) stream.

    Mirrors PDFBox ``PDType1CFont``. The font dictionary itself still
    declares ``/Subtype /Type1`` — Type1C-ness is signalled by a
    ``/FontFile3`` stream on the ``/FontDescriptor`` whose own
    ``/Subtype`` is ``Type1C``. Therefore this wrapper is *not* selected
    by ``PDFontFactory`` from the font dict's ``/Subtype`` alone; it is
    reachable today only via direct construction. Auto-dispatch from
    FontDescriptor inspection is deferred.

    The embedded CFF program is parsed lazily on first metric access
    via :class:`CFFFont` — itself a thin wrapper around
    ``fontTools.cffLib``. Glyph widths and outlines are exposed through
    :meth:`get_glyph_width` / :meth:`get_glyph_path`, inherited from
    :class:`PDType1Font` but routed through the CFF program rather than
    the Type 1 PFB-style program.
    """

    SUB_TYPE = "Type1"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        # Lazily-loaded embedded CFF program. ``None`` means
        # "not yet attempted", ``False`` means "tried, no /FontFile3 or
        # parse failed".
        self._cff: CFFFont | None | bool = None

    # ---------- CFF program access ----------

    def _get_cff_font(self) -> CFFFont | None:
        """Return the parsed CFF program for this font's
        ``/FontFile3`` stream (``/Subtype /Type1C``), or ``None`` if the
        font is not embedded or the stream cannot be parsed. Result is
        cached."""
        if self._cff is not None:
            return self._cff if isinstance(self._cff, CFFFont) else None

        descriptor = self.get_font_descriptor()
        if descriptor is None:
            self._cff = False
            return None
        font_file3 = descriptor.get_font_file3()
        if font_file3 is None:
            self._cff = False
            return None
        try:
            raw = font_file3.to_byte_array()
            self._cff = CFFFont.from_bytes(raw)
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to parse /FontFile3 for %s", self.get_name())
            self._cff = False
            return None
        return self._cff

    def set_font_program(self, font: CFFFont | None) -> None:  # type: ignore[override]
        """Inject a pre-parsed :class:`CFFFont`. Mirrors the equivalent
        injector on :class:`PDType1Font` / :class:`PDTrueTypeFont` —
        lets callers that already have the font program in hand bypass
        ``/FontFile3`` parsing, and lets tests skip the byte-level
        fixture round-trip."""
        self._cff = font if font is not None else False

    # ---------- glyph widths / paths via CFF program ----------

    def _program_width(self, code: int) -> float | None:
        """CFF-backed override of :meth:`PDType1Font._program_width`."""
        program = self._get_cff_font()
        if program is None:
            return None
        name = self._code_to_glyph_name(code)
        if name is None or not program.has_glyph(name):
            return None
        units_per_em = program.units_per_em
        if units_per_em <= 0:
            return None
        advance = program.get_width(name)
        if advance <= 0.0:
            return None
        return advance * 1000.0 / units_per_em

    def get_glyph_path(self, code: int) -> list[tuple]:  # type: ignore[override]
        """CFF-backed glyph outline for ``code``, in font units. Returns
        ``[]`` when the font has no embedded CFF program or the code is
        unmapped."""
        program = self._get_cff_font()
        if program is None:
            return []
        name = self._code_to_glyph_name(code)
        if name is None:
            return []
        return program.get_path(name)


__all__ = ["PDType1CFont"]
