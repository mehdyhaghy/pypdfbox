"""OpenType Coverage Table — Format 1 (glyph-array).

Mirrors ``org.apache.fontbox.ttf.table.common.CoverageTableFormat1``
(upstream ``CoverageTableFormat1.java`` L30-70). The upstream
``CoverageTable`` abstract base is included in this module — Python
doesn't need a separate file for a 20-line abstract class, and the task
checklist enumerates only the format implementations.
"""

from __future__ import annotations

import bisect
from abc import ABC, abstractmethod
from collections.abc import Sequence


class CoverageTable(ABC):
    """Abstract base for OpenType coverage tables.

    Mirrors ``org.apache.fontbox.ttf.table.common.CoverageTable``
    (upstream ``CoverageTable.java`` L28-47). Concrete subclasses are
    :class:`CoverageTableFormat1` (glyph-array layout) and
    :class:`CoverageTableFormat2` (range-record layout).
    """

    def __init__(self, coverage_format: int) -> None:
        self._coverage_format = coverage_format

    @abstractmethod
    def get_coverage_index(self, gid: int) -> int:
        """Return the coverage-array index of ``gid``, or a negative value
        if absent (see :meth:`CoverageTableFormat1.get_coverage_index` for
        the exact negative-encoding mirror of ``Arrays.binarySearch``)."""

    @abstractmethod
    def get_glyph_id(self, index: int) -> int:
        """Return the glyph id stored at coverage-array ``index``."""

    @abstractmethod
    def get_size(self) -> int:
        """Return the number of glyph ids in this coverage table."""

    def get_coverage_format(self) -> int:
        """Return the format byte (1 or 2)."""
        return self._coverage_format


class CoverageTableFormat1(CoverageTable):
    """Coverage table — format 1 (sorted glyph-id array).

    Mirrors ``CoverageTableFormat1.java`` L30-70. The glyph-id array is
    stored sorted ascending; lookups use a binary search whose return
    value matches Java's ``Arrays.binarySearch`` — non-negative for hits,
    ``-insertionPoint - 1`` for misses.
    """

    def __init__(self, coverage_format: int, glyph_array: Sequence[int]) -> None:
        super().__init__(coverage_format)
        # Store as an immutable tuple of ints so callers can't mutate the
        # array out from under the binary-search assumption.
        self._glyph_array: tuple[int, ...] = tuple(int(g) for g in glyph_array)

    def get_coverage_index(self, gid: int) -> int:
        """Mirror ``Arrays.binarySearch(glyphArray, gid)``
        (CoverageTableFormat1.java L42-45).

        Returns the array index of ``gid`` on hit, or
        ``-(insertion_point) - 1`` on miss — matching Java's contract so
        upstream callers that check ``index >= 0`` behave identically.
        """
        arr = self._glyph_array
        lo = bisect.bisect_left(arr, gid)
        if lo < len(arr) and arr[lo] == gid:
            return lo
        return -lo - 1

    def get_glyph_id(self, index: int) -> int:
        """Mirror ``getGlyphId(int)`` (CoverageTableFormat1.java L47-51)."""
        return self._glyph_array[index]

    def get_size(self) -> int:
        """Mirror ``getSize()`` (CoverageTableFormat1.java L53-57)."""
        return len(self._glyph_array)

    def get_glyph_array(self) -> tuple[int, ...]:
        """Mirror ``getGlyphArray()`` (CoverageTableFormat1.java L59-62).

        Upstream returns the underlying ``int[]`` (mutable view); we
        return a tuple to preserve the immutability assumption that
        :meth:`get_coverage_index` relies on. Callers needing a mutable
        copy can ``list(...)`` the result.
        """
        return self._glyph_array

    def to_string(self) -> str:
        """Mirror ``toString()`` (CoverageTableFormat1.java L64-69).

        Format: ``CoverageTableFormat1[coverageFormat=<n>,glyphArray=[...]]``
        where the glyph-array part follows Java's ``Arrays.toString`` —
        space after each comma, no trailing space.
        """
        body = ", ".join(str(g) for g in self._glyph_array)
        return (
            "CoverageTableFormat1["
            f"coverageFormat={self.get_coverage_format()},"
            f"glyphArray=[{body}]]"
        )

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["CoverageTable", "CoverageTableFormat1"]
