from __future__ import annotations

from dataclasses import dataclass

from ..model.language import Language
from .script_table import ScriptTable


@dataclass
class ScriptTableDetails:
    """Immutable triple ``(language, feature_name, script_table)``.

    Mirrors the nested ``ScriptTableDetails`` class declared inside
    ``org.apache.fontbox.ttf.gsub.GlyphSubstitutionDataExtractor``
    upstream. Promoted to a top-level class in the Python port so
    callers that want to construct one explicitly (e.g. when invoking
    :meth:`GlyphSubstitutionDataExtractor.get_gsub_data` with an
    already-chosen script) can do so without dipping into a private
    inner type.

    ``feature_name`` is the 4-byte OpenType script tag that ended up
    matching (``"latn"``, ``"deva"``, ...). Upstream named the field
    ``featureName`` even though semantically it's the script tag; we
    keep the name verbatim for parity.
    """

    language: Language
    feature_name: str
    script_table: ScriptTable

    def get_language(self) -> Language:
        return self.language

    def get_feature_name(self) -> str:
        return self.feature_name

    def get_script_table(self) -> ScriptTable:
        return self.script_table


__all__ = ["ScriptTableDetails"]
