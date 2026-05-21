"""``GsubWorkerForSMCP`` — ``smcp`` (Small Caps) GSUB worker.

Mirrors ``org.apache.fontbox.ttf.gsub.GsubWorkerForSmcp`` from upstream
Apache PDFBox 3.0.x. The class lives in the upstream *test* tree
(``fontbox/src/test/java/.../gsub/GsubWorkerForSmcp.java``) as a copy of
:class:`GsubWorkerForLatin` retargeted at the ``smcp`` feature; pypdfbox
promotes it into the main module tree so callers that want Small-Caps
shaping can ask the factory for it rather than hand-rolling the loop
themselves.

The upstream constructor takes a :class:`CmapLookup` even though
``apply_transforms`` never consults it; we keep the constructor shape
identical so callers translating from Java can pass the same arguments.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .gsub_worker import GsubWorker, _adapt_feature, _apply_gsub_feature

if TYPE_CHECKING:
    from ..cmap_lookup import CmapLookup
    from .gsub_data import GsubData

_LOG = logging.getLogger(__name__)

# Feature order from GsubWorkerForSmcp.java:44 — single ``smcp`` entry.
_FEATURES_IN_ORDER: tuple[str, ...] = ("smcp",)


class GsubWorkerForSMCP(GsubWorker):
    """``smcp``-only worker for Small Capitals substitution.

    Applies the ``smcp`` feature when the GSUB carries it; falls
    through unchanged otherwise. Mirrors upstream's test-tree shape: the
    ``cmap_lookup`` argument is accepted for upstream constructor parity
    (upstream's class also stores it without using it).
    """

    def __init__(self, cmap_lookup: CmapLookup, gsub_data: GsubData) -> None:
        self._cmap_lookup = cmap_lookup
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


__all__ = ["GsubWorkerForSMCP"]
