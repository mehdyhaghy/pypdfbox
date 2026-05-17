"""Wave 1345: residual coverage for ``GsubWorkerForBengali``.

Targets:
  - the ``script_feature is None`` continue branch (line 101);
  - the ``init`` feature path that augments the before-half glyph-id set
    (lines 167-175).
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.gsub import GsubData, GsubWorkerForBengali


class _FakeCmap(CmapLookup):
    def __init__(self, mapping: dict[int, int]) -> None:
        self._mapping = mapping

    def get_glyph_id(self, code_point_at: int) -> int:
        return self._mapping.get(code_point_at, 0)

    def get_char_codes(self, gid: int) -> list[int] | None:
        return [cp for cp, g in self._mapping.items() if g == gid] or None


def _bengali_cmap() -> _FakeCmap:
    return _FakeCmap(
        {
            ord("ি"): 101,
            ord("ে"): 102,
            ord("ৈ"): 103,
            ord("ো"): 104,
            ord("ৌ"): 105,
            ord("া"): 110,
            ord("ৗ"): 111,
        }
    )


def test_apply_transforms_skips_feature_when_adapt_returns_none() -> None:
    """``is_feature_supported`` returns True but the feature dict is None
    (signaling the adapter to return ``None``) — the worker continues past
    that feature without touching the glyph list (line 100-101)."""
    # Mark "locl" as present but supply ``None`` as its substitution map.
    gd = GsubData(
        language="BENGALI",
        feature_list={"locl": None},  # type: ignore[dict-item]
    )
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    # No substitution / no repositioning; pass-through.
    assert worker.apply_transforms([1, 2, 3]) == [1, 2, 3]


def test_init_feature_extends_before_half_glyph_ids() -> None:
    """When ``init`` is supported, the worker harvests substitution-cluster
    replacements and treats them as additional before-half glyphs.

    Setup: ``init`` substitutes the single-glyph key (200,) -> (201,).
    After construction, glyph id 201 should be recognised as a before-half
    glyph and trigger the swap during ``reposition_before_half_glyph_ids``.
    """
    gd = GsubData(
        language="BENGALI",
        feature_list={"init": {(200,): (201,)}},
    )
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    # Glyph 201 should now appear in the before-half list.
    assert 201 in worker._before_half_glyph_ids
    # Drive ``reposition_before_half_glyph_ids`` directly so we exercise
    # the augmented list without re-running the GSUB pipeline (the pipeline
    # would also try to apply the init feature itself).
    repositioned = worker.reposition_before_half_glyph_ids([50, 201])
    assert repositioned == [201, 50]


def test_init_feature_with_no_clusters_does_not_extend() -> None:
    """If ``init`` is in the feature list but has no eligible single-glyph
    substitutions, the before-half list remains unchanged."""
    gd = GsubData(
        language="BENGALI",
        feature_list={"init": {(200, 201): (300, 301)}},  # multi-glyph sub
    )
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    # Only the three statically-known before-half glyph ids survive.
    assert sorted(worker._before_half_glyph_ids) == [101, 102, 103]
