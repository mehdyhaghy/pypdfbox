from __future__ import annotations

from abc import ABC, abstractmethod


class ByteSource(ABC):
    """Source from which bytes may be read in the future.

    Mirrors the upstream nested interface
    ``org.apache.fontbox.cff.CFFParser.ByteSource``. PDFBox expresses this
    as a public inner interface of ``CFFParser``; we surface it as a
    standalone module so other clusters (e.g. ``CFFTable``) can import it
    without pulling in the parser.
    """

    @abstractmethod
    def get_bytes(self) -> bytes:
        """Return the source bytes. May be called more than once.

        Implementations must return the same logical content on every call
        — callers cache the result and rely on stable identity for
        re-parsing scenarios (Type1C subsetting, CID fallback parsing).
        """
