"""Format 0 (sequential) embedded CFF encoding.

Extracted from upstream ``CFFParser.Format0Encoding`` (PDFBox 3.0,
``CFFParser.java`` lines ~1471-1486 inclusive). The Java original is a
``private static class`` inside ``CFFParser``; pypdfbox lifts it into
its own module for cleaner test isolation.

Format 0 lays the encoding out as a flat sequence of single-byte codes
where the parser populates one (code, sid) pair per byte read after the
``nCodes`` count. This class itself doesn't parse — the parser
populates it via inherited :meth:`CFFBuiltInEncoding.add` and
:meth:`add_supplement`.
"""

from __future__ import annotations

from .cff_built_in_encoding import CFFBuiltInEncoding


class Format0Encoding(CFFBuiltInEncoding):
    """Concrete Format 0 embedded encoding.

    Parameters
    ----------
    n_codes:
        The number of (code, sid) pairs in the encoding table, taken
        from the format 0 header byte. Stored only for diagnostic /
        ``__repr__`` parity with upstream ``toString()``.
    """

    def __init__(self, n_codes: int) -> None:
        super().__init__()
        self._n_codes: int = int(n_codes)

    @property
    def n_codes(self) -> int:
        """The number of explicit (code, sid) entries in this encoding."""
        return self._n_codes

    def to_string(self) -> str:
        """PDFBox: ``CFFParser.Format0Encoding.toString()``
        (``CFFParser.java`` lines 1481-1485):
        ``getClass().getName() + "[nCodes=" + nCodes + ", supplement=" +
        Arrays.toString(super.supplement) + "]"``.

        ``Arrays.toString`` renders as ``[a, b, c]`` (comma + space) — we
        match that formatting so re-syncs are diff-clean.
        """
        cls = f"{type(self).__module__}.{type(self).__name__}"
        joined = ", ".join(repr(s) for s in self.supplement)
        return f"{cls}[nCodes={self._n_codes}, supplement=[{joined}]]"

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}[nCodes={self._n_codes}, "
            f"supplement={list(self.supplement)!r}]"
        )


__all__ = ["Format0Encoding"]
