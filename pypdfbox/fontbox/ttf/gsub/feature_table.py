from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FeatureTable:
    """OpenType Feature table — the body each ``FeatureRecord`` points at.

    Mirrors ``org.apache.fontbox.ttf.gsub.FeatureTable``. A feature
    table simply enumerates the lookup indices that a feature applies,
    plus a reserved ``feature_params`` offset (always ``0`` in current
    OT specs, but kept for fidelity).
    """

    feature_params: int = 0
    lookup_list_indices: tuple[int, ...] = field(default_factory=tuple)

    def get_feature_params(self) -> int:
        return self.feature_params

    def get_lookup_list_indices(self) -> tuple[int, ...]:
        return self.lookup_list_indices

    def get_lookup_index_count(self) -> int:
        """Return the number of lookup-list indices in this feature.

        Mirrors upstream ``FeatureTable.getLookupIndexCount()``. Upstream
        stores this as a redundant explicit field on the table; we derive
        it from the canonical ``lookup_list_indices`` sequence so the two
        cannot drift out of sync.
        """
        return len(self.lookup_list_indices)

    def __str__(self) -> str:
        """Mirror upstream ``FeatureTable.toString()``.

        Upstream formats as ``FeatureTable[lookupListIndicesCount=<N>]``;
        keep the exact string so log-grepping tooling that scrapes
        PDFBox logs continues to work against the Python port.
        """
        return f"FeatureTable[lookupListIndicesCount={len(self.lookup_list_indices)}]"


__all__ = ["FeatureTable"]
