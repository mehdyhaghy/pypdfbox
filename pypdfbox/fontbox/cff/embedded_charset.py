"""Marker base :class:`EmbeddedCharset`.

Ported from ``org.apache.fontbox.cff.EmbeddedCharset``
(``fontbox/src/main/java/org/apache/fontbox/cff/EmbeddedCharset.java``
lines 23-85).

Upstream wraps a ``CFFCharset`` and delegates every interface method to
it, picking ``CFFCharsetCID`` or ``CFFCharsetType1`` based on the
``isCIDFont`` constructor flag. We keep that pattern unchanged: the
class is concrete and forwards each call to the inner charset.
"""

from __future__ import annotations

from .cff_charset import CFFCharset
from .cff_charset_cid import CFFCharsetCID
from .cff_charset_type1 import CFFCharsetType1


class EmbeddedCharset(CFFCharset):
    """A CFF charset embedded in the font; delegates to a CID or Type1 charset."""

    def __init__(self, is_cid_font: bool) -> None:
        # Upstream lines 27-30.
        self._charset: CFFCharset = (
            CFFCharsetCID() if is_cid_font else CFFCharsetType1()
        )

    def get_cid_for_gid(self, gid: int) -> int:
        # Upstream line 32-36.
        return self._charset.get_cid_for_gid(gid)

    def is_cid_font(self) -> bool:
        # Upstream line 38-42.
        return self._charset.is_cid_font()

    def add_sid(self, gid: int, sid: int, name: str) -> None:
        # Upstream line 44-48.
        self._charset.add_sid(gid, sid, name)

    def add_cid(self, gid: int, cid: int) -> None:
        # Upstream line 50-54.
        self._charset.add_cid(gid, cid)

    def get_sid_for_gid(self, gid: int) -> int:
        # Upstream line 56-60.
        return self._charset.get_sid_for_gid(gid)

    def get_gid_for_sid(self, sid: int) -> int:
        # Upstream line 62-66.
        return self._charset.get_gid_for_sid(sid)

    def get_gid_for_cid(self, cid: int) -> int:
        # Upstream line 68-72.
        return self._charset.get_gid_for_cid(cid)

    def get_sid(self, name: str) -> int:
        # Upstream line 74-78.
        return self._charset.get_sid(name)

    def get_name_for_gid(self, gid: int) -> str | None:
        # Upstream line 80-84.
        return self._charset.get_name_for_gid(gid)
