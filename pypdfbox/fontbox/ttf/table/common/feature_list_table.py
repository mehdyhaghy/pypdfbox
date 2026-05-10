"""OpenType FeatureList table.

Mirrors ``org.apache.fontbox.ttf.table.common.FeatureListTable``
(upstream ``FeatureListTable.java`` L28-56). FeatureRecord lives at
``pypdfbox.fontbox.ttf.gsub.feature_record`` — see the import below — so
that the existing GSUB feature-record port stays single-sourced.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...gsub.feature_record import FeatureRecord


class FeatureListTable:
    """List of feature records present in a GSUB or GPOS table.

    Mirrors ``FeatureListTable.java`` L28-55. The upstream class is a
    simple value holder over ``(int featureCount, FeatureRecord[]
    featureRecords)``.
    """

    def __init__(
        self,
        feature_count: int,
        feature_records: Sequence[FeatureRecord],
    ) -> None:
        self._feature_count = int(feature_count)
        self._feature_records: tuple[FeatureRecord, ...] = tuple(feature_records)

    def get_feature_count(self) -> int:
        """Mirror ``getFeatureCount()`` (FeatureListTable.java L39-42)."""
        return self._feature_count

    def get_feature_records(self) -> tuple[FeatureRecord, ...]:
        """Mirror ``getFeatureRecords()`` (FeatureListTable.java L44-47).

        Upstream returns the mutable ``FeatureRecord[]``; we return a
        tuple to keep the table immutable. Callers needing a mutable
        sequence can ``list(...)`` the result.
        """
        return self._feature_records

    def to_string(self) -> str:
        """Mirror ``toString()`` (FeatureListTable.java L49-54).

        Upstream format: ``FeatureListTable[featureCount=<n>]``.
        """
        return f"FeatureListTable[featureCount={self._feature_count}]"

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["FeatureListTable"]
