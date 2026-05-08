from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .lookup_table import LookupTable
from .script_table import ScriptTable


@dataclass
class GsubData:
    """Top-level container for an OpenType GSUB table's parsed structure.

    Mirrors ``org.apache.fontbox.ttf.gsub.GsubData`` from upstream
    Apache PDFBox 3.0.x. ``GsubData`` is the root value object the GSUB
    parser produces — it bundles the ScriptList, the FeatureList (modeled
    as ``feature_tag -> {feature_name -> [LookupTable, ...]}`` keyed by
    *script* and then by *feature tag*), and the resolved lookup tables.

    * ``language`` is the active language hint that the consumer should
      use when looking up script-specific feature lists (typically
      ``"DEFAULT"`` for unknown). Upstream models this as the
      ``Language`` enum; we use the enum's ``getName()`` string to keep
      things storage-format-friendly without forcing a Python enum port.
    * ``active_script_name`` is the four-byte OpenType script tag
      currently being processed (``"latn"``, ``"deva"``, ``"thai"``,
      ...).
    * ``script_list`` is keyed by 4-byte script tag and holds the
      :class:`ScriptTable` for that script.
    * ``feature_list`` is the same shape upstream uses: keyed by feature
      tag (``"liga"``, ``"sups"``, ...) returning the FeatureTable-style
      mapping ``{glyph_run -> [substitute_glyph]}`` once the GSUB has
      been compiled to a substitution lookup. We keep the shape generic
      (``dict[str, list[int]]``) because the *exact* shape upstream uses
      is constructed on demand from the lookup graph.
    * ``glyph_substitution_map`` is the precomputed glyph-run-to-glyph
      substitution map (the output of
      ``GsubWorker.applyTransforms``) that consumers use directly.

    The :meth:`is_feature_supported` and :meth:`get_feature_table`
    helpers mirror upstream so consumers can branch on supported features
    without inspecting internal dicts.
    """

    language: str = "DEFAULT"
    active_script_name: str = ""
    script_list: dict[str, ScriptTable] = field(default_factory=dict)
    feature_list: dict[str, dict[tuple[int, ...], tuple[int, ...]]] = field(
        default_factory=dict
    )
    glyph_substitution_map: dict[tuple[int, ...], tuple[int, ...]] = field(
        default_factory=dict
    )
    lookup_tables: tuple[LookupTable, ...] = field(default_factory=tuple)
    NO_DATA_FOUND: ClassVar[GsubData]

    # ------------------------------------------------------------------
    # Upstream-shaped getters
    # ------------------------------------------------------------------

    def get_language(self) -> str:
        return self.language

    def get_active_script_name(self) -> str:
        return self.active_script_name

    def get_script_list(self) -> dict[str, ScriptTable]:
        return self.script_list

    def get_feature_list(
        self,
    ) -> dict[str, dict[tuple[int, ...], tuple[int, ...]]]:
        return self.feature_list

    def get_glyph_substitution_map(
        self,
    ) -> dict[tuple[int, ...], tuple[int, ...]]:
        return self.glyph_substitution_map

    def get_lookup_tables(self) -> tuple[LookupTable, ...]:
        return self.lookup_tables

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_feature_supported(self, feature_tag: str) -> bool:
        """``True`` when ``feature_tag`` exists in the FeatureList.

        Mirrors ``GsubData.isFeatureSupported`` upstream.
        """
        return feature_tag in self.feature_list

    def get_feature_table(
        self, feature_tag: str
    ) -> dict[tuple[int, ...], tuple[int, ...]] | None:
        """Per-feature substitution map, or ``None`` if absent.

        Mirrors ``GsubData.getFeatureTable``.
        """
        return self.feature_list.get(feature_tag)

    def get_feature(
        self, feature_name: str
    ) -> dict[tuple[int, ...], tuple[int, ...]] | None:
        """Per-feature substitution map, or ``None`` if absent.

        Mirrors ``GsubData.getFeature(String featureName)`` upstream.
        Upstream returns a ``ScriptFeature`` value object whose data
        boils down to ``feature_name`` plus the per-feature substitution
        map; we keep the substitution map shape that all other accessors
        already speak (and that ``apply_substitution_lookup_list``
        consumes), so consumers don't need a second value-class hop.
        """
        return self.feature_list.get(feature_name)

    def get_supported_features(self) -> set[str]:
        """Set of feature tags supported by this GSUB data.

        Mirrors ``GsubData.getSupportedFeatures()`` upstream. Returns a
        fresh ``set`` each call so callers can mutate freely without
        corrupting the underlying ``feature_list`` keys (Python sets
        aren't shareably immutable, and copying tag strings is cheap).
        """
        return set(self.feature_list.keys())

    def apply_substitution_lookup_list(
        self, glyph_ids: list[int]
    ) -> list[int]:
        """Apply the precomputed :attr:`glyph_substitution_map` to a glyph run.

        Walks ``glyph_ids`` left-to-right looking for the longest input
        run that matches a key in :attr:`glyph_substitution_map`; on a
        match, the matched run is replaced with the mapped substitution
        sequence. Returns a new list — the input is not mutated.

        Upstream's ``GsubWorker`` carries the equivalent logic in its
        ``applyTransforms`` method; we expose a standalone helper here
        because pypdfbox callers exercise it directly when shaping
        complex scripts that haven't been routed through the full
        worker pipeline yet.
        """
        if not glyph_ids or not self.glyph_substitution_map:
            return list(glyph_ids)
        # Precompute max key length so we can cap the inner loop.
        max_key = max(len(k) for k in self.glyph_substitution_map)
        out: list[int] = []
        i = 0
        n = len(glyph_ids)
        while i < n:
            matched = False
            for length in range(min(max_key, n - i), 0, -1):
                key = tuple(glyph_ids[i : i + length])
                sub = self.glyph_substitution_map.get(key)
                if sub is not None:
                    out.extend(sub)
                    i += length
                    matched = True
                    break
            if not matched:
                out.append(glyph_ids[i])
                i += 1
        return out


class _NoDataFoundGsubData(GsubData):
    """Sentinel used when a font carries no GSUB data.

    Mirrors upstream's ``GsubData.NO_DATA_FOUND`` anonymous class — every
    accessor raises rather than silently returning empty values, so
    callers are forced to guard with ``is GsubData.NO_DATA_FOUND``
    before reading anything.
    """

    def get_language(self) -> str:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def get_active_script_name(self) -> str:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def get_script_list(self) -> dict[str, ScriptTable]:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def get_feature_list(
        self,
    ) -> dict[str, dict[tuple[int, ...], tuple[int, ...]]]:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def get_glyph_substitution_map(
        self,
    ) -> dict[tuple[int, ...], tuple[int, ...]]:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def get_lookup_tables(self) -> tuple[LookupTable, ...]:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def is_feature_supported(self, feature_tag: str) -> bool:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def get_feature_table(
        self, feature_tag: str
    ) -> dict[tuple[int, ...], tuple[int, ...]] | None:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def get_feature(
        self, feature_name: str
    ) -> dict[tuple[int, ...], tuple[int, ...]] | None:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def get_supported_features(self) -> set[str]:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")

    def apply_substitution_lookup_list(
        self, glyph_ids: list[int]
    ) -> list[int]:
        raise NotImplementedError("NO_DATA_FOUND has no GSUB data")


# Class-level sentinel matching upstream ``GsubData.NO_DATA_FOUND``.
GsubData.NO_DATA_FOUND = _NoDataFoundGsubData()


__all__ = ["GsubData"]
