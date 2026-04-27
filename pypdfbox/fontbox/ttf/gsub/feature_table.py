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


__all__ = ["FeatureTable"]
