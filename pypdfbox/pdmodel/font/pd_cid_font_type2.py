from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSStream

from .pd_cid_font import PDCIDFont

if TYPE_CHECKING:
    from .pd_type0_font import PDType0Font


class PDCIDFontType2(PDCIDFont):
    """CIDFontType2 — TrueType-based CIDFont. Mirrors PDFBox ``PDCIDFontType2``.

    Lite — wraps the dictionary surface, CID width tables, and
    ``/CIDToGIDMap`` interpretation. TrueType program parsing and
    font-program metrics are deferred to the fontbox cluster.
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

        Until full Type0 CMap decoding lands, the code is treated as the
        CID. This keeps the public shape aligned with PDFBox while making
        the current Identity-CMap descendant path usable.
        """
        return self.cid_to_gid(code)

    def _code_to_gid(self, code: int, ttf: object | None = None) -> int:
        """Renderer-facing hook mirroring ``PDTrueTypeFont._code_to_gid``."""
        return self.code_to_gid(code)

    def has_cid_to_gid_map(self) -> bool:
        return self._get_cid_to_gid_map_values() is not None

    def clear_cid_to_gid_map_cache(self) -> None:
        self._cid_to_gid_cache = None
        self._cid_to_gid_cache_loaded = False

    def _get_cid_to_gid_map_values(self) -> tuple[int, ...] | None:
        if self._cid_to_gid_cache_loaded:
            return self._cid_to_gid_cache
        raw = self.get_cid_to_gid_map()
        if raw is None or raw == "Identity":
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


__all__ = ["PDCIDFontType2"]
