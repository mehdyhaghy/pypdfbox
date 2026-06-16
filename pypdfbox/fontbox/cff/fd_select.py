from __future__ import annotations

from typing import Any


class FDSelect:
    """CFF /FDSelect — maps each GID to a Font DICT index in the
    /FDArray of a CIDKeyed (Type 0) CFF font.

    Mirrors upstream ``org.apache.fontbox.cff.FDSelect`` (abstract base).
    Two on-disk formats exist (CFF spec §19):

    * **Format 0** — one byte per GID, a simple flat array.
    * **Format 3** — RLE-style ranges of ``[first, fd]`` plus a sentinel.

    fontTools normalises both formats into a single
    ``fontTools.cffLib.FDSelect`` whose ``__getitem__`` returns the
    Font DICT index for a given GID and whose ``format`` attribute
    records the original on-disk encoding. We wrap that to expose the
    PDFBox surface (``get_fd_index(gid)`` / ``get_format()`` /
    ``get_num_glyphs()``).
    """

    def __init__(self, fdselect: Any | None = None) -> None:
        # ``fdselect`` is a ``fontTools.cffLib.FDSelect`` (or any object
        # implementing ``__getitem__`` / ``__len__`` / ``.format``).
        self._fdselect = fdselect

    @classmethod
    def from_fonttools(cls, fdselect: Any) -> FDSelect:
        return cls(fdselect)

    # ---------- PDFBox-style accessors ----------

    def get_format(self) -> int:
        """PDFBox: ``FDSelect.getFormat()`` — 0 or 3 per CFF spec §19."""
        if self._fdselect is None:
            return 0
        try:
            return int(getattr(self._fdselect, "format", 0))
        except (TypeError, ValueError):
            return 0

    def get_num_glyphs(self) -> int:
        """PDFBox: ``FDSelect.getNumGlyphs()`` — number of GIDs covered."""
        if self._fdselect is None:
            return 0
        try:
            return max(0, len(self._fdselect))
        except (TypeError, ValueError):
            return 0

    def get_fd_index(self, gid: int) -> int:
        """PDFBox: ``FDSelect.getFDIndex(int gid)`` — the /FDArray index
        assigned to ``gid``. Returns 0 for any out-of-range GID, matching
        the upstream contract that an empty/short FDSelect implicitly
        maps everything to FontDict 0.
        """
        if self._fdselect is None or gid < 0:
            return 0
        try:
            return int(self._fdselect[gid])
        except (IndexError, KeyError, TypeError, ValueError):
            return 0

    # ---------- conveniences ----------

    def __len__(self) -> int:
        return self.get_num_glyphs()

    def __getitem__(self, gid: int) -> int:
        return self.get_fd_index(gid)

    def __contains__(self, gid: object) -> bool:
        """Whether ``gid`` falls inside the covered range ``[0, num_glyphs)``.
        Mirrors the Pythonic membership test; upstream PDFBox has no direct
        equivalent (callers typically clamp before calling ``getFDIndex``)."""
        if not isinstance(gid, int) or isinstance(gid, bool):
            return False
        return 0 <= gid < self.get_num_glyphs()

    def __repr__(self) -> str:
        return f"FDSelect(format={self.get_format()}, num_glyphs={self.get_num_glyphs()})"


class Format0FDSelect(FDSelect):
    """Format 0 FDSelect — flat byte array, one entry per GID.

    Mirrors upstream ``org.apache.fontbox.cff.CFFParser.Format0FDSelect``.
    Useful when a caller needs to materialise a fresh FDSelect from a
    Python ``list[int]`` (e.g. in a font writer round-trip) without going
    through fontTools' parser.
    """

    def __init__(self, fds: list[int] | None = None) -> None:
        super().__init__(None)
        self._fds: list[int] = list(fds) if fds is not None else []

    def get_format(self) -> int:
        return 0

    def get_num_glyphs(self) -> int:
        return len(self._fds)

    def get_fd_index(self, gid: int) -> int:
        if 0 <= gid < len(self._fds):
            try:
                return int(self._fds[gid])
            except (TypeError, ValueError):
                return 0
        return 0

    def __len__(self) -> int:
        return len(self._fds)

    def __getitem__(self, gid: int) -> int:
        return self.get_fd_index(gid)

    def get_fds(self) -> list[int]:
        """Return a copy of the raw per-GID Font DICT byte array.

        Mirrors upstream ``CFFParser.Format0FDSelect``'s package-private
        ``int[] fds`` field — exposed here so writers / round-trip tests
        can re-serialise the on-disk Format 0 payload.
        """
        return list(self._fds)

    def to_string(self) -> str:
        """PDFBox: ``Format0FDSelect.toString()``.

        Mirrors upstream ``CFFParser.java`` line 1161-1163:
        ``getClass().getName() + "[fds=" + Arrays.toString(fds) + "]"``.
        ``Arrays.toString(int[])`` renders as ``[1, 2, 3]`` (comma + space) —
        we match that formatting exactly so re-syncs are diff-clean.
        """
        cls = type(self).__name__
        joined = ", ".join(str(int(x)) for x in self._fds)
        return f"{cls}[fds=[{joined}]]"

    def __repr__(self) -> str:
        return self.to_string()


class Format3FDSelect(FDSelect):
    """Format 3 FDSelect — run-length ranges of ``[first, fd]`` pairs
    terminated by a sentinel ``sentinel`` (one past the last GID).

    Mirrors upstream ``org.apache.fontbox.cff.CFFParser.Format3FDSelect``.

    ``ranges`` is a list of ``(first_gid, fd_index)`` pairs, sorted by
    ``first_gid``; ``sentinel`` is the GID one past the highest GID
    covered (so each range covers ``[first_i, first_{i+1})`` and the
    final range is closed off by the sentinel).
    """

    def __init__(
        self,
        ranges: list[tuple[int, int]] | None = None,
        sentinel: int = 0,
    ) -> None:
        super().__init__(None)
        self._ranges: list[tuple[int, int]] = (
            list(ranges) if ranges is not None else []
        )
        self._sentinel = max(0, int(sentinel))

    def get_format(self) -> int:
        return 3

    def get_num_glyphs(self) -> int:
        return self._sentinel

    def get_fd_index(self, gid: int) -> int:
        # Upstream ``CFFParser$Format3FDSelect.getFDIndex`` (verified by
        # disassembly) does NOT short-circuit on a zero/empty sentinel — it
        # walks the ranges unconditionally and returns 0 only when no range
        # matches (the for-loop falls through). A GID that lands in the *last*
        # range but is at or past the sentinel returns -1, regardless of the
        # sentinel's value. We therefore guard only the genuinely
        # range-independent cases: a negative GID (upstream's loop returns 0
        # for it because every ``range3[i].first`` is >= 0 and the loop falls
        # through) and an empty range array (the loop never runs -> 0).
        if gid < 0 or not self._ranges:
            return 0
        # Linear scan mirroring PDFBox's Format3FDSelect range walk.
        for i, (first, fd) in enumerate(self._ranges):
            if gid < first:
                continue
            if i + 1 < len(self._ranges):
                next_first = self._ranges[i + 1][0]
                if gid < next_first:
                    return int(fd)
                continue
            if gid < self._sentinel:
                return int(fd)
            return -1
        return 0

    def __len__(self) -> int:
        return self._sentinel

    def __getitem__(self, gid: int) -> int:
        return self.get_fd_index(gid)

    def get_ranges(self) -> list[tuple[int, int]]:
        """Return a copy of the ``(first_gid, fd_index)`` ranges.

        Mirrors upstream ``CFFParser.Format3FDSelect``'s package-private
        ``Range3[] range3`` field — exposed for inspection / re-serialisation.
        """
        return list(self._ranges)

    def get_sentinel(self) -> int:
        """The sentinel GID (one past the last covered GID).

        Mirrors upstream ``CFFParser.Format3FDSelect``'s package-private
        ``sentinel`` field — needed when re-serialising to the on-disk
        Format 3 payload (CFF spec §19, Table 28).
        """
        return self._sentinel

    def get_num_ranges(self) -> int:
        """Number of ``(first_gid, fd_index)`` ranges. Equivalent to
        the on-disk ``nRanges`` field of CFF Format 3 FDSelect."""
        return len(self._ranges)

    def to_string(self) -> str:
        """PDFBox: ``Format3FDSelect.toString()``.

        Mirrors upstream ``CFFParser.java`` lines 1110-1113:
        ``getClass().getName() + "[nbRanges=" + range3.length + ", range3="
        + Arrays.toString(range3) + " sentinel=" + sentinel + "]"``.

        The inner ``Range3.toString()`` (line 1132-1135) renders as
        ``Range3[first=<n>, fd=<n>]`` — we use a Pythonic ``Range3``
        label rather than the Java fully-qualified name to keep the
        output stable across re-syncs (upstream uses ``getClass().getName()``
        which embeds the outer ``CFFParser$`` prefix).
        """
        cls = type(self).__name__
        ranges_str = ", ".join(
            f"Range3[first={int(first)}, fd={int(fd)}]"
            for first, fd in self._ranges
        )
        return (
            f"{cls}[nbRanges={len(self._ranges)}, range3=[{ranges_str}]"
            f" sentinel={self._sentinel}]"
        )

    def __repr__(self) -> str:
        return self.to_string()


__all__ = ["FDSelect", "Format0FDSelect", "Format3FDSelect"]
