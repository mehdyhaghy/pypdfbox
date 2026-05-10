"""Range record used by :class:`CoverageTableFormat2`.

Mirrors ``org.apache.fontbox.ttf.table.common.RangeRecord`` (upstream
``RangeRecord.java`` L28-62).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RangeRecord:
    """One (start_glyph_id, end_glyph_id, start_coverage_index) triple.

    Mirrors ``RangeRecord.java`` L30-39. ``start_coverage_index`` is the
    coverage index of ``start_glyph_id`` — subsequent glyph IDs in the
    range have monotonically increasing coverage indices.
    """

    start_glyph_id: int = 0
    end_glyph_id: int = 0
    start_coverage_index: int = 0

    def get_start_glyph_id(self) -> int:
        """Mirror ``getStartGlyphID()`` (RangeRecord.java L41-44)."""
        return self.start_glyph_id

    def get_end_glyph_id(self) -> int:
        """Mirror ``getEndGlyphID()`` (RangeRecord.java L46-49)."""
        return self.end_glyph_id

    def get_start_coverage_index(self) -> int:
        """Mirror ``getStartCoverageIndex()`` (RangeRecord.java L51-54)."""
        return self.start_coverage_index

    def to_string(self) -> str:
        """Mirror ``toString()`` (RangeRecord.java L56-61).

        Upstream format:
        ``RangeRecord[startGlyphID=%d,endGlyphID=%d,startCoverageIndex=%d]``.
        """
        return (
            "RangeRecord["
            f"startGlyphID={self.start_glyph_id},"
            f"endGlyphID={self.end_glyph_id},"
            f"startCoverageIndex={self.start_coverage_index}]"
        )

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["RangeRecord"]
