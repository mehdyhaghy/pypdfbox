"""``GsubWorkerForGujarati`` — Gujarati script GSUB worker.

Mirrors ``org.apache.fontbox.ttf.gsub.GsubWorkerForGujarati`` from
upstream Apache PDFBox 3.0.x. Structurally identical to
:class:`GsubWorkerForDevanagari` (same pipeline, same reph adjustment,
same i-matra repositioning, same rkrf-from-vatu synthesis) — only the
script-specific Unicode code points differ.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .gsub_worker import GsubWorker, _adapt_feature, _apply_gsub_feature

if TYPE_CHECKING:
    from ..cmap_lookup import CmapLookup
    from .gsub_data import GsubData

_LOG = logging.getLogger(__name__)

_RKRF_FEATURE = "rkrf"
_VATU_FEATURE = "vatu"

# Feature order from GsubWorkerForGujarati.java:50.
_FEATURES_IN_ORDER: tuple[str, ...] = (
    "locl",
    "nukt",
    "akhn",
    "rphf",
    _RKRF_FEATURE,
    "blwf",
    "half",
    _VATU_FEATURE,
    "cjct",
    "pres",
    "abvs",
    "blws",
    "psts",
    "haln",
    "calt",
)

# Reph glyphs: Gujarati RA (U+0AB0) + VIRAMA (U+0ACD). From
# GsubWorkerForGujarati.java:55.
_REPH_CHARS: tuple[str, ...] = ("ર", "્")
# Glyphs that should precede reph. From line 57.
_BEFORE_REPH_CHARS: tuple[str, ...] = ("ા", "ી")
# Gujarati vowel sign I. From line 60.
_BEFORE_HALF_CHAR = "િ"


class GsubWorkerForGujarati(GsubWorker):
    """Gujarati-script worker with reph adjustment and i-matra reposition."""

    def __init__(self, cmap_lookup: CmapLookup, gsub_data: GsubData) -> None:
        self._cmap_lookup = cmap_lookup
        self._gsub_data = gsub_data
        self._before_half_glyph_ids: list[int] = self.get_before_half_glyph_ids()
        self._reph_glyph_ids: list[int] = self.get_reph_glyph_ids()
        self._before_reph_glyph_ids: list[int] = self.get_before_reph_glyph_ids()

    # ------------------------------------------------------------------
    # GsubWorker
    # ------------------------------------------------------------------

    def apply_transforms(self, original_glyph_ids: list[int]) -> list[int]:
        intermediate = self.adjust_reph_position(list(original_glyph_ids))
        intermediate = self.reposition_glyphs(intermediate)
        for feature_tag in _FEATURES_IN_ORDER:
            if not self._gsub_data.is_feature_supported(feature_tag):
                if feature_tag == _RKRF_FEATURE and self._gsub_data.is_feature_supported(
                    _VATU_FEATURE
                ):
                    vatu_feature = _adapt_feature(
                        _VATU_FEATURE, self._gsub_data.get_feature(_VATU_FEATURE)
                    )
                    if vatu_feature is not None:
                        intermediate = self.apply_rkrf_feature(vatu_feature, intermediate)
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

    # ------------------------------------------------------------------
    # rkrf synthesis (from vatu, when rkrf isn't directly present)
    # ------------------------------------------------------------------

    def apply_rkrf_feature(
        self,
        rkrf_glyphs_for_substitution,
        original_glyph_ids: list[int],
    ) -> list[int]:
        """Mirrors GsubWorkerForGujarati.java:111."""
        rkrf_glyph_ids = rkrf_glyphs_for_substitution.get_all_glyph_ids_for_substitution()
        if not rkrf_glyph_ids:
            _LOG.debug(
                "Glyph substitution list for %s is empty.",
                rkrf_glyphs_for_substitution.get_name(),
            )
            return original_glyph_ids

        rkrf_replacement = 0
        for first_list in rkrf_glyph_ids:
            if len(first_list) > 1:
                rkrf_replacement = first_list[1]
                break
        if rkrf_replacement == 0:
            _LOG.debug(
                "Cannot find rkrf candidate. The rkrfGlyphIds doesn't contain "
                "lists of two elements."
            )
            return original_glyph_ids

        rkrf_list = list(original_glyph_ids)
        index = len(original_glyph_ids) - 1
        while index > 1:
            ra_glyph = original_glyph_ids[index]
            if ra_glyph == self._reph_glyph_ids[0]:
                virama_glyph = original_glyph_ids[index - 1]
                if virama_glyph == self._reph_glyph_ids[1]:
                    rkrf_list[index - 1] = rkrf_replacement
                    rkrf_list.pop(index)
            index -= 1
        return rkrf_list

    # ------------------------------------------------------------------
    # Repositioning helpers
    # ------------------------------------------------------------------

    def adjust_reph_position(self, original_glyph_ids: list[int]) -> list[int]:
        """Mirrors GsubWorkerForGujarati.java:186."""
        adjusted = list(original_glyph_ids)
        for index in range(len(original_glyph_ids) - 2):
            ra_glyph = original_glyph_ids[index]
            virama_glyph = original_glyph_ids[index + 1]
            if (
                ra_glyph == self._reph_glyph_ids[0]
                and virama_glyph == self._reph_glyph_ids[1]
            ):
                next_consonant = original_glyph_ids[index + 2]
                adjusted[index] = next_consonant
                adjusted[index + 1] = ra_glyph
                adjusted[index + 2] = virama_glyph
                if index + 3 < len(original_glyph_ids):
                    matra_glyph = original_glyph_ids[index + 3]
                    if matra_glyph in self._before_reph_glyph_ids:
                        adjusted[index + 1] = matra_glyph
                        adjusted[index + 2] = ra_glyph
                        adjusted[index + 3] = virama_glyph
        return adjusted

    def reposition_glyphs(self, original_glyph_ids: list[int]) -> list[int]:
        """Mirrors GsubWorkerForGujarati.java:157."""
        repositioned = list(original_glyph_ids)
        list_size = len(repositioned)
        found_index = list_size - 1
        next_index = list_size - 2
        while next_index > -1:
            if found_index >= len(repositioned) or found_index < 0:
                found_index = next_index
                next_index -= 1
                continue
            glyph = repositioned[found_index]
            prev_index = found_index + 1
            if glyph in self._before_half_glyph_ids:
                repositioned.pop(found_index)
                repositioned.insert(next_index, glyph)
                next_index -= 1
            elif (
                self._reph_glyph_ids
                and len(self._reph_glyph_ids) > 1
                and self._reph_glyph_ids[1] == glyph
                and prev_index < list_size
                and prev_index < len(repositioned)
            ):
                prev_glyph = repositioned[prev_index]
                if prev_glyph in self._before_half_glyph_ids:
                    repositioned.pop(prev_index)
                    repositioned.insert(next_index, prev_glyph)
                    next_index -= 1
            found_index = next_index
            next_index -= 1
        return repositioned

    # ------------------------------------------------------------------
    # Cmap-driven precomputation
    # ------------------------------------------------------------------

    def get_before_half_glyph_ids(self) -> list[int]:
        return [self.get_glyph_id(_BEFORE_HALF_CHAR)]

    def get_reph_glyph_ids(self) -> list[int]:
        return [self.get_glyph_id(c) for c in _REPH_CHARS]

    def get_before_reph_glyph_ids(self) -> list[int]:
        return [self.get_glyph_id(c) for c in _BEFORE_REPH_CHARS]

    def get_glyph_id(self, character: str) -> int:
        return self._cmap_lookup.get_glyph_id(ord(character))


__all__ = ["GsubWorkerForGujarati"]
