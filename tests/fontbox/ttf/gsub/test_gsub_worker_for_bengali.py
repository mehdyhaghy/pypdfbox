"""Tests for :class:`GsubWorkerForBengali`.

The upstream JUnit test requires a real Lohit-Bengali.ttf which we
don't ship. These tests drive the worker with a synthetic
:class:`CmapLookup` and synthetic :class:`GsubData` to exercise:

* the before-half (i-kar / e-kar / ai-kar) swap pass, and
* the O-kar / OU-kar two-component decomposition pass.

The numeric glyph IDs below are arbitrary — they only need to be
internally consistent across one test.
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
    # Glyph ids picked arbitrarily but stably.
    return _FakeCmap(
        {
            ord("ি"): 101,  # i-kar (before-half)
            ord("ে"): 102,  # e-kar (before-half)
            ord("ৈ"): 103,  # ai-kar (before-half)
            ord("ো"): 104,  # o-kar (before-and-after-span original)
            ord("ৌ"): 105,  # ou-kar (before-and-after-span original)
            ord("া"): 110,  # AA-kar
            ord("ৗ"): 111,  # OU after-component
        }
    )


def test_before_half_swap_with_no_features() -> None:
    """An i-kar after a consonant should swap before it visually."""
    gd = GsubData(language="BENGALI", feature_list={})
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    # consonant=50 followed by i-kar=101 → i-kar moves before the consonant.
    assert worker.apply_transforms([50, 101]) == [101, 50]


def test_before_half_swap_runs_through_pipeline() -> None:
    gd = GsubData(language="BENGALI", feature_list={})
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    # consonant=50, e-kar=102 → e-kar swaps before; trailing 60 is untouched.
    assert worker.apply_transforms([50, 102, 60]) == [102, 50, 60]


def test_okar_decomposes_into_e_and_aa() -> None:
    """O-kar (\\u09CB) becomes e-kar before + AA-kar after."""
    gd = GsubData(language="BENGALI", feature_list={})
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    # consonant=50 followed by O-kar=104 → [e-kar=102, consonant=50, AA-kar=110]
    assert worker.apply_transforms([50, 104]) == [102, 50, 110]


def test_oukar_decomposes_into_e_and_oufollow() -> None:
    """OU-kar (\\u09CC) becomes e-kar before + \\u09D7 after."""
    gd = GsubData(language="BENGALI", feature_list={})
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    assert worker.apply_transforms([50, 105]) == [102, 50, 111]


def test_gsub_feature_applied_before_reposition() -> None:
    """akhn collapses (40, 41) -> (42,) before the repositioning pass.

    The Bengali worker's FEATURES_IN_ORDER does *not* include ``liga``;
    pick a feature that actually runs (``akhn`` is in the list).
    """
    gd = GsubData(language="BENGALI", feature_list={"akhn": {(40, 41): (42,)}})
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    # After akhn: [42, 101]; after before-half swap: [101, 42].
    assert worker.apply_transforms([40, 41, 101]) == [101, 42]


def test_empty_input() -> None:
    gd = GsubData(language="BENGALI", feature_list={})
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    assert worker.apply_transforms([]) == []


def test_pass_through_when_no_special_characters() -> None:
    gd = GsubData(language="BENGALI", feature_list={})
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    assert worker.apply_transforms([50, 51, 52]) == [50, 51, 52]
