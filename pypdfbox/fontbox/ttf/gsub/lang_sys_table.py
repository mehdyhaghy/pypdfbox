from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LangSysTable:
    """OpenType Language System table.

    Mirrors ``org.apache.fontbox.ttf.gsub.LangSysTable`` from upstream
    Apache PDFBox 3.0.x. A LangSys table selects which features are
    enabled for a given language inside a script:

    * ``lookup_order`` is reserved by the spec (always ``0`` / NULL); we
      keep it so on-disk round-trips don't drop information that some
      external tooling might want to inspect.
    * ``required_feature_index`` is ``0xFFFF`` if there is no required
      feature; otherwise it indexes into the FeatureList table.
    * ``feature_indices`` is the ordered list of feature indices the
      LangSys exposes (also indexes into the FeatureList table).
    """

    lookup_order: int = 0
    required_feature_index: int = 0xFFFF
    feature_indices: tuple[int, ...] = field(default_factory=tuple)

    # ``upstream`` getters preserved (snake_case) so callers expecting the
    # PDFBox surface still work.
    def get_lookup_order(self) -> int:
        return self.lookup_order

    def get_required_feature_index(self) -> int:
        return self.required_feature_index

    def get_feature_indices(self) -> tuple[int, ...]:
        return self.feature_indices


__all__ = ["LangSysTable"]
