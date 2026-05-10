"""Format 1 (range-based) embedded CFF encoding plus its ``Range3`` element.

Extracted from upstream ``CFFParser.Format1Encoding`` (PDFBox 3.0,
``CFFParser.java`` lines ~1488-1506 inclusive). The Java original is a
``private static class`` inside ``CFFParser``; pypdfbox lifts it into
its own module for cleaner test isolation.

Format 1 encodes the table as a list of (rangeFirst, rangeLeft) byte
pairs; the SID for each code in each range is taken from the font's
charset (``charset.getSIDForGID(gid)``). Upstream's parser populates
the encoding directly via :meth:`CFFBuiltInEncoding.add` and does not
retain the parsed ranges; this port follows that exactly but also
exposes a :class:`Range3` data class so callers and tests can describe
ranges symbolically when constructing format-1 fixtures by hand.

Note: upstream has another ``Range3`` (private inner class of
``CFFParser`` at line ~1120) used by ``Format3FDSelect`` with fields
``(first, fd)``. That one ships with the FDSelect cluster (already
ported in :mod:`pypdfbox.fontbox.cff.fd_select`); this ``Range3`` is
the encoding-context counterpart with fields ``(first, n_left, sid)``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .cff_built_in_encoding import CFFBuiltInEncoding


@dataclass(frozen=True)
class Range3:
    """A single Format 1 encoding range.

    Attributes
    ----------
    first:
        First character code in the range.
    n_left:
        Number of additional codes in the range (excluding ``first``);
        the range covers ``first, first+1, ..., first+n_left``.
    sid:
        The SID of the first glyph in the range. Provided as a
        convenience when callers build ranges by hand; the upstream
        parser actually pulls each SID per-GID from the charset rather
        than carrying it in the range struct, so it may be unset (-1)
        when the parser produces ranges.
    """

    first: int
    n_left: int
    sid: int = -1

    def to_string(self) -> str:
        """Mirror upstream ``CFFParser.Range3.toString`` formatting."""
        return (
            f"Range3[first={self.first}, n_left={self.n_left}, sid={self.sid}]"
        )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}[first={self.first}, "
            f"n_left={self.n_left}, sid={self.sid}]"
        )


class Format1Encoding(CFFBuiltInEncoding):
    """Concrete Format 1 embedded (range-based) encoding.

    Parameters
    ----------
    n_ranges:
        The number of ``Range3`` ranges in the encoding table, taken
        from the format 1 header byte.
    """

    def __init__(self, n_ranges: int) -> None:
        super().__init__()
        self._n_ranges: int = int(n_ranges)

    @property
    def n_ranges(self) -> int:
        """The number of ranges in this encoding."""
        return self._n_ranges

    def to_string(self) -> str:
        """PDFBox: ``CFFParser.Format1Encoding.toString()``
        (``CFFParser.java`` lines 1501-1505):
        ``getClass().getName() + "[nRanges=" + nRanges + ", supplement=" +
        Arrays.toString(super.supplement) + "]"``.

        ``Arrays.toString`` renders as ``[a, b, c]`` (comma + space) — we
        match that formatting so re-syncs are diff-clean.
        """
        cls = f"{type(self).__module__}.{type(self).__name__}"
        joined = ", ".join(repr(s) for s in self.supplement)
        return f"{cls}[nRanges={self._n_ranges}, supplement=[{joined}]]"

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}[nRanges={self._n_ranges}, "
            f"supplement={list(self.supplement)!r}]"
        )


__all__ = ["Format1Encoding", "Range3"]
