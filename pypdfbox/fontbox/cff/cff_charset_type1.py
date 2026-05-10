"""Concrete Type1-keyed :class:`CFFCharsetType1`.

Ported from ``org.apache.fontbox.cff.CFFCharsetType1``
(``fontbox/src/main/java/org/apache/fontbox/cff/CFFCharsetType1.java``
lines 27-109).
"""

from __future__ import annotations

from .cff_charset import CFFCharset

_EXCEPTION_MESSAGE = "Not a CIDFont"


class CFFCharsetType1(CFFCharset):
    """A CFF charset for a Type 1-keyed (non-CID) font."""

    def __init__(self) -> None:
        # Mirrors upstream maps at lines 31-36.
        self._sid_to_gid: dict[int, int] = {}
        self._gid_to_sid: dict[int, int] = {}
        self._name_to_sid: dict[str, int] = {}
        self._gid_to_name: dict[int, str] = {}

    def is_cid_font(self) -> bool:
        # Upstream line 38-41.
        return False

    def add_sid(self, gid: int, sid: int, name: str) -> None:
        # Upstream line 44-50.
        self._sid_to_gid[sid] = gid
        self._gid_to_sid[gid] = sid
        self._name_to_sid[name] = sid
        self._gid_to_name[gid] = name

    def add_cid(self, gid: int, cid: int) -> None:
        # Upstream line 53-57.
        raise RuntimeError(_EXCEPTION_MESSAGE)

    def get_sid_for_gid(self, gid: int) -> int:
        # Upstream line 59-67.
        sid = self._gid_to_sid.get(gid)
        if sid is None:
            return 0
        return sid

    def get_gid_for_sid(self, sid: int) -> int:
        # Upstream line 70-78.
        gid = self._sid_to_gid.get(sid)
        if gid is None:
            return 0
        return gid

    def get_gid_for_cid(self, cid: int) -> int:
        # Upstream line 81-85.
        raise RuntimeError(_EXCEPTION_MESSAGE)

    def get_sid(self, name: str) -> int:
        # Upstream line 87-95.
        sid = self._name_to_sid.get(name)
        if sid is None:
            return 0
        return sid

    def get_name_for_gid(self, gid: int) -> str | None:
        # Upstream line 98-102: returns Java ``null`` when absent.
        return self._gid_to_name.get(gid)

    def get_cid_for_gid(self, gid: int) -> int:
        # Upstream line 104-108.
        raise RuntimeError(_EXCEPTION_MESSAGE)
