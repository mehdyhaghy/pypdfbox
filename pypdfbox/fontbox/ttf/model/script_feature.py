from __future__ import annotations

from abc import ABC, abstractmethod


class ScriptFeature(ABC):
    """Abstract base modelling one feature inside a GSUB ScriptList.

    Mirrors the ``org.apache.fontbox.ttf.model.ScriptFeature`` Java
    interface from upstream Apache PDFBox 3.0.x. A ``ScriptFeature``
    wraps a single ``FeatureRecord`` and exposes the glyph-id sequences
    it can substitute together with the lookup result for each.

    Concrete subclasses (notably :class:`MapBackedScriptFeature`)
    materialise the feature data from the parsed GSUB tables.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return the 4-byte OpenType feature tag (e.g. ``"liga"``)."""

    @abstractmethod
    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        """Return every glyph-id sequence covered by this feature.

        Each entry is the *input* side of a substitution (a tuple of
        glyph ids the feature can collapse or replace). The returned
        set is keyed by tuple because Python lists are not hashable —
        upstream uses ``Set<List<Integer>>`` directly because Java
        ``List`` defines ``hashCode``/``equals`` structurally.
        """

    @abstractmethod
    def can_replace_glyphs(self, glyph_ids: list[int]) -> bool:
        """Return ``True`` when ``glyph_ids`` matches a substitution key.

        Mirrors upstream ``ScriptFeature.canReplaceGlyphs(List<Integer>)``.
        """

    @abstractmethod
    def get_replacement_for_glyphs(self, glyph_ids: list[int]) -> int:
        """Return the substitute glyph id for ``glyph_ids``.

        Raises :class:`NotImplementedError` (mirroring upstream's
        ``UnsupportedOperationException``) when ``glyph_ids`` is not a
        recognised substitution input. Callers should gate this with
        :meth:`can_replace_glyphs`.
        """


__all__ = ["ScriptFeature"]
