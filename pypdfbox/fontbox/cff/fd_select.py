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
    def from_fonttools(cls, fdselect: Any) -> "FDSelect":
        return cls(fdselect)

    # ---------- PDFBox-style accessors ----------

    def get_format(self) -> int:
        """PDFBox: ``FDSelect.getFormat()`` — 0 or 3 per CFF spec §19."""
        if self._fdselect is None:
            return 0
        return int(getattr(self._fdselect, "format", 0))

    def get_num_glyphs(self) -> int:
        """PDFBox: ``FDSelect.getNumGlyphs()`` — number of GIDs covered."""
        if self._fdselect is None:
            return 0
        try:
            return len(self._fdselect)
        except TypeError:
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
        except (IndexError, KeyError, TypeError):
            return 0

    # ---------- conveniences ----------

    def __len__(self) -> int:
        return self.get_num_glyphs()

    def __getitem__(self, gid: int) -> int:
        return self.get_fd_index(gid)

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
            return int(self._fds[gid])
        return 0

    def __len__(self) -> int:
        return len(self._fds)

    def __getitem__(self, gid: int) -> int:
        return self.get_fd_index(gid)


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
        self._sentinel = int(sentinel)

    def get_format(self) -> int:
        return 3

    def get_num_glyphs(self) -> int:
        return self._sentinel

    def get_fd_index(self, gid: int) -> int:
        if not self._ranges or gid < 0 or gid >= self._sentinel:
            return 0
        # Linear scan — ranges count is typically small (≤16).
        last_fd = 0
        for first, fd in self._ranges:
            if gid < first:
                break
            last_fd = fd
        return int(last_fd)

    def __len__(self) -> int:
        return self._sentinel

    def __getitem__(self, gid: int) -> int:
        return self.get_fd_index(gid)


__all__ = ["FDSelect", "Format0FDSelect", "Format3FDSelect"]
