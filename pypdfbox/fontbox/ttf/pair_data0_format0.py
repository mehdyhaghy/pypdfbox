"""Format 0 kerning pair data (sorted pair list).

Mirrors the private ``PairData0Format0`` inner class of
``org.apache.fontbox.ttf.KerningSubtable`` (upstream
``KerningSubtable.java`` L255-304). Promoted to a top-level module here
so that the same decoder can be re-used outside ``KerningSubtable`` —
parity tests in particular construct one directly.

The on-disk layout is the OpenType ``kern`` format 0:
``numPairs (uint16) searchRange (uint16) entrySelector (uint16)
rangeShift (uint16)`` then ``numPairs * (left uint16, right uint16,
value int16)`` entries sorted by ``(left, right)``.
"""

from __future__ import annotations

import bisect
from typing import TYPE_CHECKING

from .pair_data import PairData

if TYPE_CHECKING:
    from .ttf_data_stream import TTFDataStream


class PairData0Format0(PairData):
    """Sorted pair list — OpenType ``kern`` format 0.

    Mirrors ``KerningSubtable$PairData0Format0`` (KerningSubtable.java
    L255-304). Upstream stores entries as ``int[numPairs][3]`` of
    ``(left, right, value)`` rows and uses ``Arrays.binarySearch`` with
    a custom comparator. We keep that exact layout — a tuple of
    ``(left, right, value)`` triples sorted by ``(left, right)`` — so
    that :meth:`get_kerning` is a binary search over the same keys
    upstream uses, producing matching results down to value sign and
    overflow.
    """

    def __init__(self) -> None:
        # Tuple-of-triples mirrors upstream's ``int[][] pairs``. Empty
        # until :meth:`read` populates it.
        self._pairs: tuple[tuple[int, int, int], ...] = ()
        # Cached sort key view ``(left, right)`` for binary search. Built
        # lazily on first :meth:`get_kerning` call.
        self._keys: tuple[tuple[int, int], ...] | None = None

    def read(self, data: TTFDataStream) -> None:
        """Decode the format-0 pair list from ``data``.

        Mirrors ``PairData0Format0#read(TTFDataStream)``
        (KerningSubtable.java L259-276). Reads the 8-byte binary-search
        header (numPairs, searchRange, entrySelector, rangeShift) then
        ``numPairs`` (uint16 left, uint16 right, int16 value) entries.
        """
        num_pairs = data.read_unsigned_short()
        # searchRange / entrySelector / rangeShift are part of the
        # OpenType binary-search header upstream uses but our bisect
        # implementation doesn't need them. Read and discard for cursor
        # parity.
        data.read_unsigned_short()  # searchRange (already divided by 6 upstream)
        data.read_unsigned_short()  # entrySelector
        data.read_unsigned_short()  # rangeShift
        rows: list[tuple[int, int, int]] = []
        for _ in range(num_pairs):
            left = data.read_unsigned_short()
            right = data.read_unsigned_short()
            value = data.read_signed_short()
            rows.append((left, right, value))
        self._pairs = tuple(rows)
        self._keys = None

    def get_kerning(self, left: int, right: int) -> int:
        """Mirror ``PairData0Format0#getKerning(int, int)``
        (KerningSubtable.java L278-288).

        Binary-search the sorted ``(left, right, value)`` rows; return
        the value column on hit or ``0`` on miss — matching upstream's
        ``Arrays.binarySearch(pairs, key, this) >= 0`` check.
        """
        if not self._pairs:
            return 0
        if self._keys is None:
            self._keys = tuple((row[0], row[1]) for row in self._pairs)
        idx = bisect.bisect_left(self._keys, (left, right))
        if idx < len(self._keys) and self._keys[idx] == (left, right):
            return self._pairs[idx][2]
        return 0

    @staticmethod
    def compare(p1: tuple[int, ...], p2: tuple[int, ...]) -> int:
        """Mirror ``PairData0Format0#compare(int[], int[])``
        (KerningSubtable.java L290-303).

        Sorts ascending by first element, then by second. ``p1`` and
        ``p2`` must each have at least two entries — the third (value)
        is ignored, matching upstream's docstring asserting
        ``p1.length >= 2``.
        """
        if p1[0] != p2[0]:
            return (p1[0] > p2[0]) - (p1[0] < p2[0])
        return (p1[1] > p2[1]) - (p1[1] < p2[1])


__all__ = ["PairData0Format0"]
