"""``GsubWorkerForTamil`` — Tamil script GSUB worker.

Mirrors ``org.apache.fontbox.ttf.gsub.GsubWorkerForTamil`` from upstream
Apache PDFBox 3.0.x. The upstream implementation is structurally a copy
of :class:`GsubWorkerForGujarati` with Tamil reph (RA+VIRAMA: U+0BB0,
U+0BCD) / before-reph (U+0BB8, U+0BCD) / before-half (Gujarati vowel
sign I, U+0ABF — left as-is in upstream code; see upstream
``GsubWorkerForTamil.java:60`` comment "TODO adjust all below this
line").

Upstream's feature list for Tamil is taken from the Microsoft Tamil
script-development guide and differs from Gujarati by adding ``pref``
between ``rphf`` and ``half``, and by dropping ``blwf`` / ``vatu`` /
``cjct`` / ``rkrf``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .gsub_worker import GsubWorker, _adapt_feature, _apply_gsub_feature

if TYPE_CHECKING:
    from ..cmap_lookup import CmapLookup
    from .gsub_data import GsubData

_LOG = logging.getLogger(__name__)

# Feature order from GsubWorkerForTamil.java:48 — Microsoft Tamil
# script-development guide.
_FEATURES_IN_ORDER: tuple[str, ...] = (
    "locl",
    "nukt",
    "akhn",
    "rphf",
    "pref",
    "half",
    "pres",
    "abvs",
    "blws",
    "psts",
    "haln",
    "calt",
)

# Reph glyphs: Tamil RA (U+0BB0) + VIRAMA (U+0BCD). From
# GsubWorkerForTamil.java:55.
_REPH_CHARS: tuple[str, ...] = ("ர", "்")
# Glyphs that should precede reph (U+0BB8 SA + U+0BCD VIRAMA — matches
# upstream literally, see GsubWorkerForTamil.java:57 + the comment
# above).
_BEFORE_REPH_CHARS: tuple[str, ...] = ("ஸ", "்")
# "Gujarati vowel sign I" — left as upstream wrote it on the Tamil
# class (GsubWorkerForTamil.java:60). The constant itself carries a
# TODO comment in the upstream source.
_BEFORE_HALF_CHAR = "િ"


class GsubWorkerForTamil(GsubWorker):
    """Tamil-script worker with reph adjustment and before-half reposition."""

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
    # Repositioning helpers
    # ------------------------------------------------------------------

    def adjust_reph_position(self, original_glyph_ids: list[int]) -> list[int]:
        """Move RA+VIRAMA reph past the consonant it modifies.

        Mirrors GsubWorkerForTamil.java:127.
        """
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
        """Reposition before-half glyphs and reph+before-half sequences.

        Mirrors GsubWorkerForTamil.java:98. Upstream walks the list back
        to front, swapping each before-half glyph one slot earlier and
        — when the previous slot is the virama half of the reph cluster
        — also dragging the glyph one slot *after* it leftward to land
        before the reph. The Python port preserves the original index
        cursor mechanic upstream uses.
        """
        repositioned = list(original_glyph_ids)
        list_size = len(repositioned)
        found_index = list_size - 1
        next_index = list_size - 2
        while next_index > -1:
            glyph = repositioned[found_index]
            prev_index = found_index + 1
            if glyph in self._before_half_glyph_ids:
                repositioned.pop(found_index)
                repositioned.insert(next_index, glyph)
                next_index -= 1
            elif (
                glyph == self._reph_glyph_ids[1]
                and prev_index < list_size
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


__all__ = ["GsubWorkerForTamil"]
