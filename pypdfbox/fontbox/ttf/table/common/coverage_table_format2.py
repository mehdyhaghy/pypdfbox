"""OpenType Coverage Table — Format 2 (range-based).

Mirrors ``org.apache.fontbox.ttf.table.common.CoverageTableFormat2``
(upstream ``CoverageTableFormat2.java`` L31-73).
"""

from __future__ import annotations

from collections.abc import Sequence

from .coverage_table_format1 import CoverageTableFormat1
from .range_record import RangeRecord


class CoverageTableFormat2(CoverageTableFormat1):
    """Coverage table — format 2 (range records).

    Extends :class:`CoverageTableFormat1` so that the flattened glyph-id
    array — built from each :class:`RangeRecord`'s
    ``start_glyph_id .. end_glyph_id`` inclusive range — drives
    coverage-index lookups, while the originating range records remain
    accessible via :meth:`get_range_records`.

    Mirrors ``CoverageTableFormat2.java`` L31-72 line-for-line.
    """

    def __init__(
        self, coverage_format: int, range_records: Sequence[RangeRecord]
    ) -> None:
        records = tuple(range_records)
        super().__init__(coverage_format, self.get_range_records_as_array(records))
        self._range_records: tuple[RangeRecord, ...] = records

    def get_range_records(self) -> tuple[RangeRecord, ...]:
        """Mirror ``getRangeRecords()`` (CoverageTableFormat2.java L41-44)."""
        return self._range_records

    @staticmethod
    def get_range_records_as_array(
        range_records: Sequence[RangeRecord],
    ) -> tuple[int, ...]:
        """Mirror ``getRangeRecordsAsArray`` (CoverageTableFormat2.java L46-66).

        Flattens every range into the inclusive ``[start_glyph_id,
        end_glyph_id]`` sequence and concatenates the results — upstream
        uses an ``ArrayList<Integer>`` plus an ``int[]`` copy; we just
        materialise the chain into a tuple.
        """
        glyph_ids: list[int] = []
        for record in range_records:
            for gid in range(record.start_glyph_id, record.end_glyph_id + 1):
                glyph_ids.append(gid)
        return tuple(glyph_ids)

    def to_string(self) -> str:
        """Mirror ``toString()`` (CoverageTableFormat2.java L68-72).

        Format: ``CoverageTableFormat2[coverageFormat=<n>]`` — upstream
        does not list the range records here, matching by design.
        """
        return f"CoverageTableFormat2[coverageFormat={self.get_coverage_format()}]"

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["CoverageTableFormat2"]
