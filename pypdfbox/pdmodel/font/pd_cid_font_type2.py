from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .pd_cid_font import PDCIDFont

if TYPE_CHECKING:
    from .pd_type0_font import PDType0Font

_LOG = logging.getLogger(__name__)

_CID_TO_GID_MAP: COSName = COSName.get_pdf_name("CIDToGIDMap")
_IDENTITY: COSName = COSName.get_pdf_name("Identity")
_OPEN_TYPE: str = "OpenType"

# Default TrueType units-per-em — matches upstream's fallback when the
# font program is missing or could not be parsed (PDF coordinate space
# is 1000-unit, the actual em is recovered from the embedded /head when
# the program is available).
_DEFAULT_UNITS_PER_EM: int = 1000


class PDCIDFontType2(PDCIDFont):
    """CIDFontType2 — TrueType-based CIDFont. Mirrors PDFBox ``PDCIDFontType2``.

    Wraps the dictionary surface, CID width tables, ``/CIDToGIDMap``
    interpretation, and embedded ``/FontFile2`` access. Renderer-facing
    glyph paths are extracted via fontTools' glyph-set draw protocol on
    the embedded TTF.
    """

    SUB_TYPE = "CIDFontType2"

    def __init__(
        self,
        font_dict: COSDictionary | None = None,
        parent_type0_font: PDType0Font | None = None,
    ) -> None:
        super().__init__(font_dict, parent_type0_font)
        self._cid_to_gid_cache: tuple[int, ...] | None = None
        self._cid_to_gid_cache_loaded = False
        # Embedded ``/FontFile2`` parsed lazily on first glyph access.
        # ``None`` means "not yet attempted"; ``False`` means "tried,
        # no /FontFile2 or parse failed".
        self._ttf: TrueTypeFont | None | bool = None

    def get_subtype(self) -> str | None:
        return self.SUB_TYPE

    # ---------- /CIDToGIDMap interpretation ----------

    def set_cid_to_gid_map(self, value: COSStream | str | None) -> None:
        super().set_cid_to_gid_map(value)
        self.clear_cid_to_gid_map_cache()

    def cid_to_gid(self, cid: int) -> int:
        """Map a CID to a TrueType glyph ID.

        ``/CIDToGIDMap`` stream values are big-endian unsigned shorts,
        one per CID. Missing or ``/Identity`` maps use the CID as the GID.
        CIDs outside an explicit stream map resolve to GID 0, matching the
        embedded-font path in PDFBox ``PDCIDFontType2.codeToGID``.
        """
        if cid < 0:
            return 0
        mapping = self._get_cid_to_gid_map_values()
        if mapping is None:
            return int(cid)
        if cid < len(mapping):
            return mapping[cid]
        return 0

    def code_to_gid(self, code: int) -> int:
        """Return the GID for ``code``.

        Mirrors upstream ``PDCIDFontType2.codeToGID`` — the parent
        :class:`PDType0Font` has already converted character code to CID
        via the active CMap, so for the descendant CIDFontType2 the
        ``code`` argument is the CID to be mapped through ``/CIDToGIDMap``.
        """
        return self.cid_to_gid(code)

    def code_to_cid(self, code: int) -> int:
        """Identity — the parent :class:`PDType0Font` CMap has already
        mapped ``code`` to CID before this descendant is consulted.
        Mirrors upstream ``PDCIDFontType2.codeToCID``.
        """
        return int(code)

    def _code_to_gid(self, code: int, ttf: object | None = None) -> int:
        """Renderer-facing hook mirroring ``PDTrueTypeFont._code_to_gid``."""
        return self.code_to_gid(code)

    def has_cid_to_gid_map(self) -> bool:
        return self._get_cid_to_gid_map_values() is not None

    def clear_cid_to_gid_map_cache(self) -> None:
        self._cid_to_gid_cache = None
        self._cid_to_gid_cache_loaded = False

    def get_cid_to_gid_map_bytes(self) -> bytes | None:
        """Return the raw decoded bytes of the ``/CIDToGIDMap`` stream,
        or ``None`` when the entry is absent or set to the name
        ``/Identity``.

        Mirrors upstream ``PDCIDFontType2.getCIDToGIDMap`` which yields
        the stream payload (callers iterate as big-endian ``uint16``
        GIDs). The parent's :meth:`PDCIDFont.get_cid_to_gid_map` still
        exposes the raw COS entry (``COSStream | str | None``) for
        callers that need to round-trip the dictionary verbatim.
        """
        raw = self._raw_cid_to_gid_entry()
        if isinstance(raw, COSStream):
            return raw.to_byte_array()
        return None

    def is_identity_cid_to_gid_map(self) -> bool:
        """``True`` when ``/CIDToGIDMap`` is the name ``/Identity`` *or*
        is absent — the spec defaults an unset entry to ``/Identity``.
        Mirrors upstream ``PDCIDFontType2.isIdentityCIDToGIDMap``."""
        raw = self._raw_cid_to_gid_entry()
        if raw is None:
            return True
        if isinstance(raw, COSName):
            return raw.name == "Identity"
        if isinstance(raw, str):
            return raw == "Identity"
        return False

    def _raw_cid_to_gid_entry(self) -> Any:
        """Read the ``/CIDToGIDMap`` entry from the underlying dict
        without coercion — used by the upstream-named accessors that
        each interpret it differently."""
        return self._dict.get_dictionary_object(_CID_TO_GID_MAP)

    def _get_cid_to_gid_map_values(self) -> tuple[int, ...] | None:
        if self._cid_to_gid_cache_loaded:
            return self._cid_to_gid_cache
        raw = self._raw_cid_to_gid_entry()
        if raw is None:
            self._cid_to_gid_cache = None
        elif isinstance(raw, COSName):
            # /Identity -> identity mapping (None signals "use cid as gid").
            self._cid_to_gid_cache = None
        elif isinstance(raw, COSStream):
            data = raw.to_byte_array()
            usable = len(data) - (len(data) % 2)
            self._cid_to_gid_cache = tuple(
                int.from_bytes(data[i : i + 2], "big")
                for i in range(0, usable, 2)
            )
        else:
            self._cid_to_gid_cache = None
        self._cid_to_gid_cache_loaded = True
        return self._cid_to_gid_cache

    # ---------- embedded TTF program ----------

    def get_true_type_font(self) -> TrueTypeFont | None:
        """Return the parsed :class:`TrueTypeFont` for this font's
        embedded program, or ``None`` if no embedded program exists or
        it cannot be parsed. Result is cached on the instance.

        Mirrors upstream ``PDCIDFontType2.getTrueTypeFont``. Tries
        ``/FontFile2`` first (the canonical form per PDF 32000-1
        §9.6.2 Table 122); falls back to ``/FontFile3`` with
        ``/Subtype /OpenType`` (the OpenType-flavoured form permitted
        by §9.9.1 for CIDFontType2 descendants).
        """
        if self._ttf is not None:
            return self._ttf if isinstance(self._ttf, TrueTypeFont) else None

        descriptor = self.get_font_descriptor()
        if descriptor is None:
            self._ttf = False
            return None
        program_stream = descriptor.get_font_file2()
        if program_stream is None:
            font_file3 = descriptor.get_font_file3()
            if font_file3 is not None:
                subtype = font_file3.get_cos_object().get_name(
                    COSName.SUBTYPE  # type: ignore[attr-defined]
                )
                if subtype == _OPEN_TYPE:
                    program_stream = font_file3
        if program_stream is None:
            self._ttf = False
            return None
        try:
            raw = program_stream.to_byte_array()
            self._ttf = TrueTypeFont.from_bytes(raw)
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to parse font program for %s", self.get_name())
            self._ttf = False
            return None
        return self._ttf

    def set_true_type_font(self, ttf: TrueTypeFont | None) -> None:
        """Inject a pre-parsed :class:`TrueTypeFont`. Used by callers
        that already have the font program in hand (avoids a redundant
        re-parse) and by tests that bypass ``/FontFile2``."""
        self._ttf = ttf if ttf is not None else False

    def is_embedded(self) -> bool:
        """``True`` when the descriptor carries an embedded font program
        usable as a CIDFontType2.

        Mirrors upstream ``PDCIDFontType2.isEmbedded``. Accepts the
        canonical ``/FontFile2`` form (PDF 32000-1 §9.6.2 Table 122)
        and the OpenType-flavoured ``/FontFile3`` with
        ``/Subtype /OpenType`` form permitted by §9.9.1 for
        CIDFontType2 descendants of a Type 0 composite.
        """
        descriptor = self.get_font_descriptor()
        if descriptor is None:
            return False
        if descriptor.get_font_file2() is not None:
            return True
        font_file3 = descriptor.get_font_file3()
        if font_file3 is None:
            return False
        subtype = font_file3.get_cos_object().get_name(
            COSName.SUBTYPE  # type: ignore[attr-defined]
        )
        return subtype == _OPEN_TYPE

    def is_damaged(self) -> bool:
        """``True`` when the descriptor advertises an embedded font
        program but the program could not be parsed.

        Mirrors upstream ``PDCIDFontType2.isDamaged``. Returns ``False``
        when the font is not embedded (nothing to parse, nothing
        damaged) and ``False`` when the parse succeeded.
        """
        if not self.is_embedded():
            return False
        # Force the lazy parse and check whether it surfaced a real TTF.
        self.get_true_type_font()
        return self._ttf is False

    # ---------- glyph metrics from the embedded program ----------

    def get_width_from_font(self, cid: int) -> float:
        """Glyph advance for ``cid`` read directly from the embedded
        TrueType program, in 1/1000 em.

        Mirrors upstream ``PDCIDFontType2.getWidthFromFont``. Resolves
        ``cid`` to a GID via :meth:`cid_to_gid`, asks the embedded
        ``hmtx`` table for the advance, then scales by
        ``1000 / unitsPerEm`` so the result is in PDF text-space units.
        Returns ``0.0`` when no embedded program is available.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return 0.0
        try:
            gid = self.cid_to_gid(cid)
            advance = ttf.get_advance_width(gid)
            units_per_em = ttf.get_units_per_em()
        except Exception:  # noqa: BLE001
            return 0.0
        if units_per_em <= 0:
            return 0.0
        return float(advance) * 1000.0 / float(units_per_em)

    def get_height(self, cid: int) -> float:  # type: ignore[override]
        """Vertical extent of glyph ``cid`` in 1/1000 em.

        Mirrors upstream ``PDCIDFontType2.getHeight``. Reads
        ``yMax - yMin`` from the embedded ``glyf`` table for the
        resolved GID, scaled by ``1000 / unitsPerEm``. Falls back to
        the parent's ``/W2`` lookup when no embedded program is
        available.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return super().get_height(cid)
        try:
            gid = self.cid_to_gid(cid)
        except Exception:  # noqa: BLE001
            return super().get_height(cid)
        if gid <= 0:
            return super().get_height(cid)
        units_per_em = ttf.get_units_per_em()
        if units_per_em <= 0:
            return 0.0
        inner = getattr(ttf, "_tt", None)
        if inner is None or "glyf" not in inner:
            return 0.0
        try:
            order = inner.getGlyphOrder()
            if not 0 <= gid < len(order):
                return 0.0
            name = order[gid]
            glyph = inner["glyf"][name]
            y_min = int(getattr(glyph, "yMin", 0))
            y_max = int(getattr(glyph, "yMax", 0))
        except (KeyError, AttributeError):
            return 0.0
        return float(y_max - y_min) * 1000.0 / float(units_per_em)

    def get_average_font_width(self) -> float:  # type: ignore[override]
        """Mean glyph advance across the embedded program (1/1000 em).

        Mirrors upstream ``PDCIDFontType2.getAverageFontWidth``. Walks
        the embedded ``hmtx`` table and averages the *positive* advance
        widths (zero-width slots, typically ``.notdef`` and combining
        marks, are excluded so they don't drag the mean toward zero).
        Falls back to the parent's ``/W``-based average — and ultimately
        to ``/DW`` — when no embedded program is available.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return super().get_average_font_width()
        units_per_em = ttf.get_units_per_em()
        if units_per_em <= 0:
            return super().get_average_font_width()
        try:
            advances = ttf.advance_widths
        except Exception:  # noqa: BLE001
            return super().get_average_font_width()
        positive = [w for w in advances if w > 0]
        if not positive:
            return super().get_average_font_width()
        mean_units = sum(positive) / float(len(positive))
        return mean_units * 1000.0 / float(units_per_em)

    def get_font_matrix(self) -> list[float]:
        """Return the 6-element font matrix mapping glyph space to text
        space (``[1/upem 0 0 1/upem 0 0]`` for TrueType).

        Mirrors upstream ``PDCIDFontType2.getFontMatrix``. Falls back to
        a 1000-unit em (``1/1000``) when no embedded program is
        available — that matches PDF 32000-1's default for fonts with
        no explicit matrix and keeps callers from dividing by zero.
        """
        ttf = self.get_true_type_font()
        if ttf is not None:
            try:
                upem = ttf.get_units_per_em()
            except Exception:  # noqa: BLE001
                upem = _DEFAULT_UNITS_PER_EM
            if upem <= 0:
                upem = _DEFAULT_UNITS_PER_EM
        else:
            upem = _DEFAULT_UNITS_PER_EM
        scale = 1.0 / float(upem)
        return [scale, 0.0, 0.0, scale, 0.0, 0.0]

    def get_bounding_box(self) -> PDRectangle | None:  # type: ignore[override]
        """Return the font's bounding box.

        Mirrors upstream ``PDCIDFontType2.getBoundingBox``. Prefers the
        embedded TTF ``head`` table's ``[xMin yMin xMax yMax]`` (the
        true glyph-space bbox), falling back to the descriptor's
        ``/FontBBox`` when no program is available — matching the
        upstream lookup order.
        """
        ttf = self.get_true_type_font()
        if ttf is not None:
            inner = getattr(ttf, "_tt", None)
            if inner is not None and "head" in inner:
                try:
                    head = inner["head"]
                    return PDRectangle(
                        float(head.xMin),
                        float(head.yMin),
                        float(head.xMax),
                        float(head.yMax),
                    )
                except (KeyError, AttributeError):
                    pass
        return super().get_bounding_box()

    def has_glyph(self, cid: int) -> bool:  # type: ignore[override]
        """``True`` when ``cid`` resolves to a non-``.notdef`` glyph.

        Prefers the embedded TTF (a glyph maps to GID != 0); falls back
        to the parent's ``/W``/``/DW`` advance heuristic when no font
        program is available.
        """
        ttf = self.get_true_type_font()
        if ttf is not None:
            try:
                gid = self.cid_to_gid(cid)
            except Exception:  # noqa: BLE001
                return super().has_glyph(cid)
            return gid > 0
        return super().has_glyph(cid)

    def get_glyph_path(self, cid: int) -> list[tuple]:
        """Glyph outline for ``cid`` in *font units*.

        Resolves ``cid`` to a GID via :meth:`cid_to_gid`, then draws the
        TTF glyph through fontTools' glyph-set draw protocol into the
        same ``("moveto", x, y)`` / ``("lineto", x, y)`` /
        ``("curveto", x1, y1, x2, y2, x3, y3)`` / ``("closepath",)``
        format used by the Type1/CFF code path. Returns ``[]`` when no
        embedded program is available or the glyph cannot be drawn.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return []
        try:
            gid = self.cid_to_gid(cid)
            glyph_name = ttf._tt.getGlyphName(gid)  # noqa: SLF001
            glyph_set = ttf._tt.getGlyphSet()  # noqa: SLF001
            glyph = glyph_set[glyph_name]
        except Exception:  # noqa: BLE001
            return []
        from pypdfbox.fontbox.type1.type1_font import _make_path_pen  # noqa: PLC0415

        pen = _make_path_pen()
        try:
            glyph.draw(pen)
        except Exception:  # noqa: BLE001
            return []
        return list(pen.commands)  # type: ignore[attr-defined]


__all__ = ["PDCIDFontType2"]
