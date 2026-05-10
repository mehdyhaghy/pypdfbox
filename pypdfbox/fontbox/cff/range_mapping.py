"""Range mapping for Format 1 / Format 2 CFF charsets.

Ported from the package-private static class ``RangeMapping`` defined
inside ``org.apache.fontbox.cff.CFFParser`` (lines 1668-1702 of
``CFFParser.java``).

A range mapping describes a contiguous block of GIDs that map to a
contiguous block of SIDs/CIDs starting at ``first``. ``n_left`` is the
number of glyphs in the range *minus one* (so a range of length 1 has
``n_left == 0``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RangeMapping:
    """Forward and reverse mapping for a contiguous GID/SID-or-CID block."""

    start_gid: int
    first: int
    n_left: int

    @property
    def start_value(self) -> int:
        # Upstream ``startValue`` (line 1670).
        return self.start_gid

    @property
    def end_value(self) -> int:
        # Upstream ``endValue = startValue + nLeft`` (line 1678).
        return self.start_gid + self.n_left

    @property
    def start_mapped_value(self) -> int:
        # Upstream ``startMappedValue`` (line 1672).
        return self.first

    @property
    def end_mapped_value(self) -> int:
        # Upstream ``endMappedValue = startMappedValue + nLeft`` (line 1680).
        return self.first + self.n_left

    def is_in_range(self, value: int) -> bool:
        # Upstream line 1683-1686.
        return self.start_value <= value <= self.end_value

    def is_in_reverse_range(self, value: int) -> bool:
        # Upstream line 1688-1691.
        return self.start_mapped_value <= value <= self.end_mapped_value

    def map_value(self, value: int) -> int:
        # Upstream line 1693-1696.
        if self.is_in_range(value):
            return self.start_mapped_value + (value - self.start_value)
        return 0

    def map_reverse_value(self, value: int) -> int:
        # Upstream line 1698-1701.
        if self.is_in_reverse_range(value):
            return self.start_value + (value - self.start_mapped_value)
        return 0

    def to_string(self) -> str:
        """PDFBox: ``CFFParser.RangeMapping.toString()``
        (``CFFParser.java`` lines 1703-1707):
        ``getClass().getName() + "[start value=" + startValue +
        ", end value=" + endValue +  ", start mapped-value=" +
        startMappedValue +  ", end mapped-value=" + endMappedValue +"]"``.
        """
        cls = f"{type(self).__module__}.{type(self).__name__}"
        return (
            f"{cls}[start value={self.start_value}, "
            f"end value={self.end_value}, "
            f"start mapped-value={self.start_mapped_value}, "
            f"end mapped-value={self.end_mapped_value}]"
        )

    def __str__(self) -> str:
        return self.to_string()
