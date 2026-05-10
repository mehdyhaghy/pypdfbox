"""Abstract :class:`CFFCharset` base.

Ported from ``org.apache.fontbox.cff.CFFCharset``
(``fontbox/src/main/java/org/apache/fontbox/cff/CFFCharset.java`` lines
24-98). Upstream is a Java ``interface``; we model it as an abstract base
class so concrete subclasses can share a marker type and so we can hang
helpful error messages on the unimplemented methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CFFCharset(ABC):
    """A CFF charset: an array of SIDs/CIDs for all glyphs in the font."""

    @abstractmethod
    def is_cid_font(self) -> bool:
        """Indicates whether this charset belongs to a CID font.

        Mirrors upstream ``isCIDFont()`` (line 31).
        """

    @abstractmethod
    def add_sid(self, gid: int, sid: int, name: str) -> None:
        """Add a new GID/SID/name combination (upstream ``addSID``, line 40)."""

    @abstractmethod
    def add_cid(self, gid: int, cid: int) -> None:
        """Add a new GID/CID combination (upstream ``addCID``, line 48)."""

    @abstractmethod
    def get_sid_for_gid(self, gid: int) -> int:
        """Return the SID for a given GID (upstream ``getSIDForGID``, line 56)."""

    @abstractmethod
    def get_gid_for_sid(self, sid: int) -> int:
        """Return the GID for the given SID (upstream ``getGIDForSID``, line 64)."""

    @abstractmethod
    def get_gid_for_cid(self, cid: int) -> int:
        """Return the GID for a given CID, or 0 if missing (upstream
        ``getGIDForCID``, line 72)."""

    @abstractmethod
    def get_sid(self, name: str) -> int:
        """Return the SID for a given PostScript name (upstream ``getSID``,
        line 81)."""

    @abstractmethod
    def get_name_for_gid(self, gid: int) -> str | None:
        """Return the PostScript glyph name for the given GID (upstream
        ``getNameForGID``, line 89)."""

    @abstractmethod
    def get_cid_for_gid(self, gid: int) -> int:
        """Return the CID for the given GID (upstream ``getCIDForGID``,
        line 97)."""
