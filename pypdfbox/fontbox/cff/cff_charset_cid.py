"""Concrete CID-keyed :class:`CFFCharsetCID`.

Ported from ``org.apache.fontbox.cff.CFFCharsetCID``
(``fontbox/src/main/java/org/apache/fontbox/cff/CFFCharsetCID.java``
lines 27-101).
"""

from __future__ import annotations

from .cff_charset import CFFCharset

_EXCEPTION_MESSAGE = "Not a Type 1-equivalent font"


class CFFCharsetCID(CFFCharset):
    """A CFF charset for a CID-keyed font (array of CIDs for all glyphs)."""

    def __init__(self) -> None:
        # Mirrors upstream ``sidOrCidToGid`` (line 32) / ``gidToCid`` (line 35).
        self._cid_to_gid: dict[int, int] = {}
        self._gid_to_cid: dict[int, int] = {}

    def is_cid_font(self) -> bool:
        # Upstream line 38-41.
        return True

    def add_sid(self, gid: int, sid: int, name: str) -> None:
        # Upstream line 44-47: SID-based access raises on a CID charset.
        raise RuntimeError(_EXCEPTION_MESSAGE)

    def add_cid(self, gid: int, cid: int) -> None:
        # Upstream line 49-54.
        self._cid_to_gid[cid] = gid
        self._gid_to_cid[gid] = cid

    def get_sid_for_gid(self, gid: int) -> int:
        # Upstream line 56-60.
        raise RuntimeError(_EXCEPTION_MESSAGE)

    def get_gid_for_sid(self, sid: int) -> int:
        # Upstream line 62-66.
        raise RuntimeError(_EXCEPTION_MESSAGE)

    def get_gid_for_cid(self, cid: int) -> int:
        # Upstream line 68-77.
        gid = self._cid_to_gid.get(cid)
        if gid is None:
            return 0
        return gid

    def get_sid(self, name: str) -> int:
        # Upstream line 79-83.
        raise RuntimeError(_EXCEPTION_MESSAGE)

    def get_name_for_gid(self, gid: int) -> str | None:
        # Upstream line 85-89.
        raise RuntimeError(_EXCEPTION_MESSAGE)

    def get_cid_for_gid(self, gid: int) -> int:
        # Upstream line 91-100.
        cid = self._gid_to_cid.get(gid)
        if cid is not None:
            return cid
        return 0
