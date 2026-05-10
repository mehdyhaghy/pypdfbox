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

    def to_string(self) -> str:
        """Mirror upstream ``FeatureRecord.toString()``.

        Upstream format: ``FeatureRecord[featureTag=<tag>]`` (no padding
        adjustment — the raw 4-byte tag is emitted as stored, trailing
        spaces and all).
        """
        return f"FeatureRecord[featureTag={self.feature_tag}]"

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["FeatureRecord"]
