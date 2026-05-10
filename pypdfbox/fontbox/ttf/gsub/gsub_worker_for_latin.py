"""``GsubWorkerForLatin`` — Latin script GSUB worker.

Mirrors ``org.apache.fontbox.ttf.gsub.GsubWorkerForLatin`` from upstream
Apache PDFBox 3.0.x. Applies ``ccmp``, ``liga``, ``clig`` in the order
recommended by the Microsoft Latin script-development guide.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .gsub_worker import GsubWorker, _adapt_feature, _apply_gsub_feature

if TYPE_CHECKING:
    from .gsub_data import GsubData

_LOG = logging.getLogger(__name__)

# Latin-specific feature order, from GsubWorkerForLatin.java:46.
_FEATURES_IN_ORDER: tuple[str, ...] = ("ccmp", "liga", "clig")


class GsubWorkerForLatin(GsubWorker):
    """Latin-script worker that applies ``ccmp``, ``liga``, ``clig``."""

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


__all__ = ["GsubWorkerForLatin"]
