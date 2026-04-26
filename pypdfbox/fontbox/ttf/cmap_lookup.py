from __future__ import annotations

from abc import ABC, abstractmethod


class CmapLookup(ABC):
    """Abstract codepoint-to-glyph (and reverse) lookup.

    Mirrors ``org.apache.fontbox.ttf.CmapLookup`` interface.
    """

    @abstractmethod
    def get_glyph_id(self, code_point_at: int) -> int:
        """Return the glyph id for the given character code, or 0 if missing."""

    @abstractmethod
    def get_char_codes(self, gid: int) -> list[int] | None:
        """Return all character codes mapped to ``gid``, or None if none."""
