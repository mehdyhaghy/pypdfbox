"""Format 2 (range-format with 16-bit ``nLeft``) CFF charset.

Ported from the package-private static class ``Format2Charset`` defined
inside ``org.apache.fontbox.cff.CFFParser`` (lines 1618-1663 of
``CFFParser.java``).

Format 2 unconditionally uses its range list (Format 1 only does so when
the font is CID-keyed); the storage shape of the range list is
identical, only the on-disk ``nLeft`` width differs.
"""

from __future__ import annotations

from .embedded_charset import EmbeddedCharset
from .range_mapping import RangeMapping


class Format2Charset(EmbeddedCharset):
    """Format 2 range-format charset."""

    def __init__(self, is_cid_font: bool) -> None:
        super().__init__(is_cid_font)
        # Upstream line 1620.
        self._ranges_cid_to_gid: list[RangeMapping] = []

    def add_range_mapping(self, range_mapping: RangeMapping) -> None:
        # Upstream line 1633-1636.
        self._ranges_cid_to_gid.append(range_mapping)

    def get_cid_for_gid(self, gid: int) -> int:
        # Upstream line 1638-1649.
        for mapping in self._ranges_cid_to_gid:
            if mapping.is_in_range(gid):
                return mapping.map_value(gid)
        return super().get_cid_for_gid(gid)

    def get_gid_for_cid(self, cid: int) -> int:
        # Upstream line 1651-1662.
        for mapping in self._ranges_cid_to_gid:
            if mapping.is_in_reverse_range(cid):
                return mapping.map_reverse_value(cid)
        return super().get_gid_for_cid(cid)
