from __future__ import annotations

from collections.abc import Mapping

from .script_feature import ScriptFeature


class MapBackedScriptFeature(ScriptFeature):
    """Dict-backed :class:`ScriptFeature` implementation.

    Mirrors ``org.apache.fontbox.ttf.model.MapBackedScriptFeature`` from
    upstream Apache PDFBox 3.0.x. The feature data is a
    ``glyph_run -> substitute_glyph_id`` map; keys are tuples (Java uses
    ``List<Integer>`` which is hashable via structural equality, the
    Python equivalent that hashes the same way is :class:`tuple`).
    """

    def __init__(
        self,
        name: str,
        feature_map: Mapping[tuple[int, ...], int],
    ) -> None:
        self._name: str = name
        # Snapshot into a plain ``dict`` so callers can't mutate the
        # feature behind our back while we hold a reference; matches
        # the immutability upstream gets via ``Collections.unmodifiableMap``.
        self._feature_map: dict[tuple[int, ...], int] = dict(feature_map)

    def get_name(self) -> str:
        return self._name

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        return set(self._feature_map.keys())

    def can_replace_glyphs(self, glyph_ids: list[int]) -> bool:
        return tuple(glyph_ids) in self._feature_map

    def get_replacement_for_glyphs(self, glyph_ids: list[int]) -> int:
        key = tuple(glyph_ids)
        if key not in self._feature_map:
            raise NotImplementedError(
                f"The glyphs {list(glyph_ids)} cannot be replaced"
            )
        return self._feature_map[key]

    # ------------------------------------------------------------------
    # Object identity — mirror upstream ``equals`` / ``hashCode``
    # ------------------------------------------------------------------

    def __hash__(self) -> int:
        # Mirrors upstream ``Objects.hash(featureMap, name)`` —
        # ``frozenset`` over the map's items because dict ordering
        # doesn't affect Java's ``Map.hashCode`` either.
        return hash((self._name, frozenset(self._feature_map.items())))

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, MapBackedScriptFeature):
            return False
        return self._name == other._name and self._feature_map == other._feature_map

    def equals(self, other: object) -> bool:
        """Mirror upstream's Java ``equals`` method.

        Delegates to :meth:`__eq__` so Python's ``==`` operator and the
        Java-named ``equals`` API agree.
        """
        return self.__eq__(other)

    def hash_code(self) -> int:
        """Mirror upstream's Java ``hashCode`` method.

        Delegates to :meth:`__hash__` so Python's ``hash()`` builtin and
        the Java-named ``hashCode`` API agree.
        """
        return self.__hash__()


__all__ = ["MapBackedScriptFeature"]
