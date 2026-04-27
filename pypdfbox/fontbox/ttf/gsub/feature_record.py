from __future__ import annotations

from dataclasses import dataclass

from .feature_table import FeatureTable


@dataclass
class FeatureRecord:
    """One entry in the FeatureList — pairs a 4-byte feature tag with
    its FeatureTable body.

    Mirrors ``org.apache.fontbox.ttf.gsub.FeatureRecord``. ``feature_tag``
    is the OpenType feature tag string (``liga``, ``ccmp``, ``sups``,
    ...). Tags shorter than four characters are padded with spaces to
    match upstream — callers comparing tags should ``.strip()`` first.
    """

    feature_tag: str = ""
    feature_table: FeatureTable | None = None

    def get_feature_tag(self) -> str:
        return self.feature_tag

    def get_feature_table(self) -> FeatureTable | None:
        return self.feature_table


__all__ = ["FeatureRecord"]
