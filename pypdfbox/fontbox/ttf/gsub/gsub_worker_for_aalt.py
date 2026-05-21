"""``GsubWorkerForAALT`` — ``aalt`` (Access All Alternates) GSUB worker.

Mirrors ``org.apache.fontbox.ttf.gsub.GsubWorkerForAalt`` from upstream
Apache PDFBox 3.0.x. The class lives in the upstream *test* tree
(``fontbox/src/test/java/.../gsub/GsubWorkerForAalt.java``) as a copy of
:class:`GsubWorkerForLatin` retargeted at the ``aalt`` feature; pypdfbox
promotes it into the main module tree so callers that want
Access-All-Alternates shaping can ask the factory for it rather than
hand-rolling the loop themselves.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .gsub_worker import GsubWorker, _adapt_feature, _apply_gsub_feature

if TYPE_CHECKING:
    from .gsub_data import GsubData

_LOG = logging.getLogger(__name__)

# Feature order from GsubWorkerForAalt.java:43 — single ``aalt`` entry.
_FEATURES_IN_ORDER: tuple[str, ...] = ("aalt",)


class GsubWorkerForAALT(GsubWorker):
    """``aalt``-only worker for Access All Alternates substitution.

    Applies the ``aalt`` feature (OpenType Type 3 alternate substitution)
    when the GSUB carries it; falls through unchanged otherwise. Matches
    upstream's per-feature shape — no script-specific reordering, no
    cmap dependency, just split-then-substitute against the alternate
    set.
    """

    def __init__(self, gsub_data: GsubData) -> None:
        self._gsub_data = gsub_data

    def apply_transforms(self, original_glyph_ids: list[int]) -> list[int]:
        intermediate: list[int] = list(original_glyph_ids)
        for feature_tag in _FEATURES_IN_ORDER:
            if not self._gsub_data.is_feature_supported(feature_tag):
                _LOG.debug("the feature %s was not found", feature_tag)
                continue
            _LOG.debug("applying the feature %s", feature_tag)
            script_feature = _adapt_feature(
                feature_tag, self._gsub_data.get_feature(feature_tag)
            )
            if script_feature is None:
                continue
            intermediate = self.apply_gsub_feature(script_feature, intermediate)
        return intermediate

    def apply_gsub_feature(self, script_feature, original_glyphs: list[int]) -> list[int]:
        """Apply ``script_feature`` to ``original_glyphs``.

        Mirrors upstream's per-worker ``applyGsubFeature`` private
        method; delegates to the shared helper that all workers use.
        """
        return _apply_gsub_feature(script_feature, original_glyphs)


__all__ = ["GsubWorkerForAALT"]
