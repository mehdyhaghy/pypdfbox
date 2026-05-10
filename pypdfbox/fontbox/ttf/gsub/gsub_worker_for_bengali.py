"""``GsubWorkerForBengali`` — Bengali script GSUB worker.

Mirrors ``org.apache.fontbox.ttf.gsub.GsubWorkerForBengali`` from
upstream Apache PDFBox 3.0.x. Applies Bengali-specific GSUB features in
the order recommended by the Microsoft Bengali script-development guide,
then runs two repositioning passes (``before-half`` swap and
``before-and-after-span`` decomposition) to match upstream's display
ordering of i-kar, e-kar, o-kar and ou-kar matras.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .gsub_worker import GsubWorker, _adapt_feature, _apply_gsub_feature

if TYPE_CHECKING:
    from ..cmap_lookup import CmapLookup
    from .gsub_data import GsubData

_LOG = logging.getLogger(__name__)

_INIT_FEATURE = "init"

# Feature order from GsubWorkerForBengali.java:52.
_FEATURES_IN_ORDER: tuple[str, ...] = (
    "locl",
    "nukt",
    "akhn",
    "rphf",
    "blwf",
    "pstf",
    "half",
    "vatu",
    "cjct",
    _INIT_FEATURE,
    "pres",
    "abvs",
    "blws",
    "psts",
    "haln",
    "calt",
)

# Bengali "before half" characters that visually precede the
# consonant they logically follow (i-kar, e-kar, ai-kar). From
# GsubWorkerForBengali.java:56.
_BEFORE_HALF_CHARS: tuple[str, ...] = ("ি", "ে", "ৈ")


@dataclass(frozen=True)
class _BeforeAndAfterSpanComponent:
    """Two-component matra that splits into a before- and after-component.

    Models O-kar (``ো``) and OU-kar (``ৌ``) — each is rendered
    as two glyphs flanking the consonant they logically follow. Mirrors
    the nested ``BeforeAndAfterSpanComponent`` class at
    GsubWorkerForBengali.java:233.
    """

    original_character: str
    before_component_character: str
    after_component_character: str


# From GsubWorkerForBengali.java:57.
_BEFORE_AND_AFTER_SPAN_CHARS: tuple[_BeforeAndAfterSpanComponent, ...] = (
    _BeforeAndAfterSpanComponent("ো", "ে", "া"),
    _BeforeAndAfterSpanComponent("ৌ", "ে", "ৗ"),
)


class GsubWorkerForBengali(GsubWorker):
    """Bengali-script worker with i-kar/e-kar/o-kar/ou-kar repositioning."""

    def __init__(self, cmap_lookup: CmapLookup, gsub_data: GsubData) -> None:
        self._cmap_lookup = cmap_lookup
        self._gsub_data = gsub_data
        self._before_half_glyph_ids: list[int] = self.get_before_half_glyph_ids()
        self._before_and_after_span_glyph_ids: dict[
            int, _BeforeAndAfterSpanComponent
        ] = self.get_before_and_after_span_glyph_ids()

    # ------------------------------------------------------------------
    # GsubWorker
    # ------------------------------------------------------------------

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
        return self.reposition_glyphs(intermediate)

    def apply_gsub_feature(self, script_feature, original_glyphs: list[int]) -> list[int]:
        """Apply ``script_feature`` to ``original_glyphs``.

        Mirrors upstream's per-worker ``applyGsubFeature`` private
        method; delegates to the shared helper that all workers use.
        """
        return _apply_gsub_feature(script_feature, original_glyphs)

    # ------------------------------------------------------------------
    # Repositioning helpers
    # ------------------------------------------------------------------

    def reposition_glyphs(self, original_glyph_ids: list[int]) -> list[int]:
        repositioned = self.reposition_before_half_glyph_ids(original_glyph_ids)
        return self.reposition_before_and_after_span_glyph_ids(repositioned)

    def reposition_before_half_glyph_ids(
        self, original_glyph_ids: list[int]
    ) -> list[int]:
        """Swap each before-half glyph with its preceding glyph.

        Mirrors GsubWorkerForBengali.java:107.
        """
        out = list(original_glyph_ids)
        for index in range(1, len(original_glyph_ids)):
            glyph_id = original_glyph_ids[index]
            if glyph_id in self._before_half_glyph_ids:
                previous_glyph_id = original_glyph_ids[index - 1]
                out[index] = previous_glyph_id
                out[index - 1] = glyph_id
        return out

    def reposition_before_and_after_span_glyph_ids(
        self, original_glyph_ids: list[int]
    ) -> list[int]:
        """Decompose O-kar / OU-kar into their two-component form.

        Mirrors GsubWorkerForBengali.java:124.
        """
        out = list(original_glyph_ids)
        # We iterate over the *original* indices but mutate ``out``; that
        # matches upstream's pattern of indexing into the unchanged
        # ``originalGlyphIds`` while writing into the repositioned list.
        index = 1
        while index < len(original_glyph_ids):
            glyph_id = original_glyph_ids[index]
            component = self._before_and_after_span_glyph_ids.get(glyph_id)
            if component is not None:
                previous_glyph_id = original_glyph_ids[index - 1]
                out[index] = previous_glyph_id
                out[index - 1] = self.get_glyph_id(component.before_component_character)
                out.insert(index + 1, self.get_glyph_id(component.after_component_character))
            index += 1
        return out

    # ------------------------------------------------------------------
    # Cmap-driven precomputation
    # ------------------------------------------------------------------

    def get_before_half_glyph_ids(self) -> list[int]:
        glyph_ids: list[int] = [self.get_glyph_id(c) for c in _BEFORE_HALF_CHARS]
        if self._gsub_data.is_feature_supported(_INIT_FEATURE):
            init_feature = _adapt_feature(
                _INIT_FEATURE, self._gsub_data.get_feature(_INIT_FEATURE)
            )
            if init_feature is not None:
                for cluster in init_feature.get_all_glyph_ids_for_substitution():
                    # ``cluster`` here is the glyph-run key; upstream
                    # passes it straight to ``getReplacementForGlyphs``
                    # which returns the replacement glyph id.
                    glyph_ids.append(
                        init_feature.get_replacement_for_glyphs(list(cluster))
                    )
        return glyph_ids

    def get_before_and_after_span_glyph_ids(
        self,
    ) -> dict[int, _BeforeAndAfterSpanComponent]:
        out: dict[int, _BeforeAndAfterSpanComponent] = {}
        for component in _BEFORE_AND_AFTER_SPAN_CHARS:
            out[self.get_glyph_id(component.original_character)] = component
        return out

    def get_glyph_id(self, character: str) -> int:
        return self._cmap_lookup.get_glyph_id(ord(character))


__all__ = ["GsubWorkerForBengali"]
