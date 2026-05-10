from __future__ import annotations

from collections.abc import Mapping

from .language import Language
from .map_backed_script_feature import MapBackedScriptFeature
from .script_feature import ScriptFeature


class MapBackedGsubData:
    """Dict-backed GSUB data container.

    Mirrors ``org.apache.fontbox.ttf.model.MapBackedGsubData`` from
    upstream Apache PDFBox 3.0.x. The class implements the upstream
    ``GsubData`` Java interface; rather than introduce a second
    abstract base in the Python port (the existing
    :class:`pypdfbox.fontbox.ttf.gsub.gsub_data.GsubData` already
    plays that role with a different shape), we keep the method
    surface upstream uses on the interface verbatim so callers can
    duck-type either implementation.

    ``glyph_substitution_map`` is keyed by feature tag and each value
    is the ``glyph_run -> substitute_glyph_id`` map for that feature.
    """

    def __init__(
        self,
        language: Language,
        active_script_name: str,
        glyph_substitution_map: Mapping[str, Mapping[tuple[int, ...], int]],
    ) -> None:
        self._language: Language = language
        self._active_script_name: str = active_script_name
        # Snapshot the outer dict so callers can't reorder features
        # after construction. Inner maps are kept as-is — upstream
        # wraps them in ``Collections.unmodifiableMap`` at write time
        # rather than copying.
        self._glyph_substitution_map: dict[str, Mapping[tuple[int, ...], int]] = dict(
            glyph_substitution_map
        )

    def get_language(self) -> Language:
        return self._language

    def get_active_script_name(self) -> str:
        return self._active_script_name

    def is_feature_supported(self, feature_name: str) -> bool:
        return feature_name in self._glyph_substitution_map

    def get_feature(self, feature_name: str) -> ScriptFeature:
        if not self.is_feature_supported(feature_name):
            raise NotImplementedError(
                f"The feature {feature_name} is not supported!"
            )
        return MapBackedScriptFeature(
            feature_name, self._glyph_substitution_map[feature_name]
        )

    def get_supported_features(self) -> set[str]:
        return set(self._glyph_substitution_map.keys())


__all__ = ["MapBackedGsubData"]
