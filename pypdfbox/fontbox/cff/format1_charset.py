"""Format 1 (range-format) CFF charset.

Ported from the package-private static class ``Format1Charset`` defined
inside ``org.apache.fontbox.cff.CFFParser`` (lines 1562-1613 of
``CFFParser.java``).

Format 1 is the 8-bit ``nLeft`` range-format charset; it extends
:class:`EmbeddedCharset` and overrides CID lookups with a list-of-ranges
walk for CID-keyed fonts.
"""

from __future__ import annotations

from .embedded_charset import EmbeddedCharset
from .range_mapping import RangeMapping


class Format1Charset(EmbeddedCharset):
    """Format 1 range-format charset (``addRangeMapping`` per upstream)."""

    def __init__(self, is_cid_font: bool) -> None:
        super().__init__(is_cid_font)
        # Upstream line 1564.
        self._ranges_cid_to_gid: list[RangeMapping] = []

    def add_range_mapping(self, range_mapping: RangeMapping) -> None:
        # Upstream line 1577-1580.
        self._ranges_cid_to_gid.append(range_mapping)

    def get_cid_for_gid(self, gid: int) -> int:
        # Upstream line 1582-1596.
        if self.is_cid_font():
            for mapping in self._ranges_cid_to_gid:
                if mapping.is_in_range(gid):
                    return mapping.map_value(gid)
        return super().get_cid_for_gid(gid)

    def get_gid_for_cid(self, cid: int) -> int:
        # Upstream line 1598-1612.
        if self.is_cid_font():
            for mapping in self._ranges_cid_to_gid:
                if mapping.is_in_reverse_range(cid):
                    return mapping.map_reverse_value(cid)
        return super().get_gid_for_cid(cid)
