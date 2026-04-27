from __future__ import annotations

import logging
from typing import Any

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

    # ---------- font identity ----------

    def get_base_font(self) -> str | None:
        """Alias for :meth:`get_name` — mirrors upstream's split between
        ``getName()`` and ``getBaseFont()`` on simple fonts (both read
        ``/BaseFont``).
        """
        return self.get_name()

    # ---------- TTF program access ----------

    def get_true_type_font(self) -> TrueTypeFont | None:
        """Return the parsed :class:`TrueTypeFont` for this font's
        ``/FontFile2`` stream, or ``None`` if the font is not embedded
        or the stream cannot be parsed. Result is cached.

        Mirrors upstream ``PDTrueTypeFont.getTrueTypeFont``. The leading
        underscore variant remains as the historical internal entry
        point and now simply delegates here.
        """
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

    def _get_true_type_font(self) -> TrueTypeFont | None:
        """Internal alias retained for callers that pre-date the public
        :meth:`get_true_type_font` accessor."""
        return self.get_true_type_font()

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

        ttf = self.get_true_type_font()
        if ttf is None:
            return 0.0

        gid = self._code_to_gid(code, ttf)
        units_per_em = ttf.get_units_per_em()
        if units_per_em <= 0:
            return 0.0
        advance = ttf.get_advance_width(gid)
        return advance * 1000.0 / units_per_em

    # ---------- displacement / vertical metrics ----------

    def get_displacement(self, code: int) -> tuple[float, float]:
        """Glyph displacement vector ``(tx, ty)`` for a character code.

        Simple fonts are written horizontally only — the displacement
        is ``(width / 1000, 0)`` per PDF 32000-1 §9.2.4. Mirrors upstream
        ``PDSimpleFont.getDisplacement``.
        """
        return (self.get_glyph_width(code) / 1000.0, 0.0)

    def get_height(self, code: int) -> float:
        """Glyph bounding-box height for ``code`` in font units.

        Reads the ``yMax - yMin`` extent of the glyph in the embedded
        ``glyf`` table; returns ``0.0`` when no embedded TTF is
        available, the code does not resolve to a glyph, or the
        font has no ``glyf`` table (e.g. CFF-based OpenType).
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return 0.0
        gid = self._code_to_gid(code, ttf)
        if gid <= 0:
            return 0.0
        return _glyph_bbox_height(ttf, gid)

    # ---------- glyph paths ----------

    def get_path(self, name: str) -> list[tuple]:
        """Glyph outline for the PostScript glyph ``name``, in font units.

        Returns the recorded pen segments emitted by fontTools' glyph
        set. Each segment is a ``(verb, args)`` tuple where ``verb`` is
        one of ``"moveTo"``, ``"lineTo"``, ``"curveTo"``, ``"qCurveTo"``,
        or ``"closePath"`` and ``args`` is the corresponding tuple of
        coordinates. Returns an empty list when the font is not embedded
        or the glyph is unknown.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return []
        return _draw_glyph_by_name(ttf, name)

    def get_glyph_path(self, code: int) -> list[tuple]:
        """Glyph outline for character ``code``, in font units.

        Resolves ``code`` to a glyph through the encoding (via
        :meth:`get_glyph_name_for_code`) when possible, falling back to
        a direct ``code -> gid`` cmap lookup for symbolic / no-encoding
        fonts. Returns an empty list when no glyph can be drawn.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return []
        name = self.get_glyph_name_for_code(code)
        if name:
            path = _draw_glyph_by_name(ttf, name)
            if path:
                return path
        gid = self._code_to_gid(code, ttf)
        if gid <= 0:
            return []
        return _draw_glyph_by_gid(ttf, gid)

    # ---------- code -> glyph name ----------

    def get_glyph_name_for_code(self, code: int) -> str | None:
        """Resolve a 1-byte character code to a PostScript glyph name
        via the font's ``/Encoding`` (with ``/Differences`` overlay).

        Returns ``None`` for ``.notdef`` and unmapped codes — callers
        treat that as "no glyph available". Mirrors upstream
        ``PDTrueTypeFont.getGlyphNameForCode``.
        """
        encoding = self.get_encoding_typed()
        if encoding is None:
            return None
        name = encoding.get_name(code)
        if not name or name == ".notdef":
            return None
        return name

    # ---------- code -> glyph_id ----------

    def code_to_gid(self, code: int) -> int:
        """Public ``code → glyph id`` mapping.

        Symbolic fonts (``/Flags`` bit 3 set, no usable ``/Encoding``):
        the code *is* the glyph id. Nonsymbolic fonts: route through
        the ``/Encoding`` to a glyph name, then to the cmap. Returns
        ``0`` (the ``.notdef`` glyph) when no mapping is found.

        Mirrors upstream ``PDTrueTypeFont.codeToGID``.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            # No embedded program — for symbolic fonts the convention is
            # still "code is GID"; otherwise we have no answer.
            return code if self.is_symbolic() else 0
        return self._code_to_gid(code, ttf)

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


# ---------- module-level helpers (fontTools shim) ----------


def _fonttools_glyph_set(ttf: TrueTypeFont) -> Any | None:
    """Return the fontTools ``GlyphSet`` for ``ttf``, or ``None`` when the
    underlying font has no drawable glyphs (rare — should only happen for
    deeply broken inputs)."""
    inner = getattr(ttf, "_tt", None)
    if inner is None:
        return None
    try:
        return inner.getGlyphSet()
    except Exception:  # noqa: BLE001 — fontTools may raise on malformed tables
        _LOG.exception("getGlyphSet failed")
        return None


def _gid_to_glyph_name(ttf: TrueTypeFont, gid: int) -> str | None:
    inner = getattr(ttf, "_tt", None)
    if inner is None:
        return None
    try:
        order = inner.getGlyphOrder()
    except Exception:  # noqa: BLE001
        return None
    if 0 <= gid < len(order):
        return str(order[gid])
    return None


def _draw_glyph_by_name(ttf: TrueTypeFont, name: str) -> list[tuple]:
    glyph_set = _fonttools_glyph_set(ttf)
    if glyph_set is None or name not in glyph_set:
        return []
    try:
        from fontTools.pens.recordingPen import RecordingPen  # noqa: PLC0415

        pen = RecordingPen()
        glyph_set[name].draw(pen)
    except Exception:  # noqa: BLE001 — unparsable charstrings should not crash callers
        _LOG.exception("recordingPen draw failed for glyph %s", name)
        return []
    return list(pen.value)


def _draw_glyph_by_gid(ttf: TrueTypeFont, gid: int) -> list[tuple]:
    name = _gid_to_glyph_name(ttf, gid)
    if name is None:
        return []
    return _draw_glyph_by_name(ttf, name)


def _glyph_bbox_height(ttf: TrueTypeFont, gid: int) -> float:
    """Height of glyph ``gid``'s on-curve bounding box in font units.

    Reads the ``glyf`` table directly when present (TTF outline fonts).
    Falls back to drawing the glyph through the fontTools glyph set and
    measuring the recorded segments — covers CFF-shaped paths embedded
    inside an OpenType-flavoured ``/FontFile2`` stream, even though that
    is not strictly a conforming PDF. Returns ``0.0`` when nothing
    drawable is found.
    """
    inner = getattr(ttf, "_tt", None)
    if inner is None:
        return 0.0
    name = _gid_to_glyph_name(ttf, gid)
    if name is None:
        return 0.0
    if "glyf" in inner:
        try:
            glyph = inner["glyf"][name]
            y_min = int(getattr(glyph, "yMin", 0))
            y_max = int(getattr(glyph, "yMax", 0))
            return float(y_max - y_min)
        except (KeyError, AttributeError):
            return 0.0
    # CFF-style fallback via the bounding-box pen.
    try:
        from fontTools.pens.boundsPen import BoundsPen  # noqa: PLC0415

        glyph_set = _fonttools_glyph_set(ttf)
        if glyph_set is None or name not in glyph_set:
            return 0.0
        pen = BoundsPen(glyph_set)
        glyph_set[name].draw(pen)
        if pen.bounds is None:
            return 0.0
        _, y_min, _, y_max = pen.bounds
        return float(y_max - y_min)
    except Exception:  # noqa: BLE001
        return 0.0


__all__ = ["PDTrueTypeFont"]
