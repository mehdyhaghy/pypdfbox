from __future__ import annotations

from abc import ABC, abstractmethod


class GlyphArraySplitter(ABC):
    """Abstract base for "split an array of glyph ids on substitution sites".

    Mirrors the ``org.apache.fontbox.ttf.gsub.GlyphArraySplitter`` Java
    interface from upstream Apache PDFBox 3.0.x. Concrete
    implementations (notably :class:`GlyphArraySplitterRegexImpl`) take
    a set of substitution input sequences and split arbitrary glyph
    runs into chunks where each chunk is either an exact match for one
    of the substitution inputs or a run of "pass through" glyphs.
    """

    @abstractmethod
    def split(self, glyph_ids: list[int]) -> list[list[int]]:
        """Return ``glyph_ids`` split on the configured substitution sites.

        Each entry in the returned list is itself a list of glyph ids.
        Matched substitution inputs and non-matched runs alternate.
        """


__all__ = ["GlyphArraySplitter"]
