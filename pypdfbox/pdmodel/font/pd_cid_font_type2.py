from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont

from .pd_cid_font import PDCIDFont

if TYPE_CHECKING:
    from .pd_type0_font import PDType0Font

_LOG = logging.getLogger(__name__)

_CID_TO_GID_MAP: COSName = COSName.get_pdf_name("CIDToGIDMap")
_IDENTITY: COSName = COSName.get_pdf_name("Identity")


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
        ``/FontFile2`` stream, or ``None`` if the descriptor lacks one
        or the program cannot be parsed. Result is cached on the
        instance. Mirrors upstream ``PDCIDFontType2.getTrueTypeFont``.
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

    def set_true_type_font(self, ttf: TrueTypeFont | None) -> None:
        """Inject a pre-parsed :class:`TrueTypeFont`. Used by callers
        that already have the font program in hand (avoids a redundant
        re-parse) and by tests that bypass ``/FontFile2``."""
        self._ttf = ttf if ttf is not None else False

    def is_embedded(self) -> bool:
        """``True`` when the descriptor carries a ``/FontFile2`` stream
        — the only embedding form a CIDFontType2 may legally use per
        PDF 32000-1 §9.6.2 (Table 122 / §9.9.1)."""
        descriptor = self.get_font_descriptor()
        if descriptor is None:
            return False
        return descriptor.get_font_file2() is not None

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
