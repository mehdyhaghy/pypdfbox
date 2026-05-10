"""Tests for :class:`GsubWorkerForDevanagari`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.gsub import GsubData, GsubWorkerForDevanagari


class _FakeCmap(CmapLookup):
    def __init__(self, mapping: dict[int, int]) -> None:
        self._mapping = mapping

    def get_glyph_id(self, code_point_at: int) -> int:
        return self._mapping.get(code_point_at, 0)

    def get_char_codes(self, gid: int) -> list[int] | None:
        return [cp for cp, g in self._mapping.items() if g == gid] or None


def _deva_cmap() -> _FakeCmap:
    return _FakeCmap(
        {
            ord("र"): 200,  # RA (reph[0])
            ord("्"): 201,  # VIRAMA (reph[1])
            ord("ा"): 202,  # AA-matra (before-reph)
            ord("ी"): 203,  # II-matra (before-reph)
            ord("ि"): 204,  # I-matra (before-half)
        }
    )


def test_pass_through_basic_consonants() -> None:
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    assert worker.apply_transforms([10, 11, 12]) == [10, 11, 12]


def test_reph_position_adjusted_past_consonant() -> None:
    """RA + VIRAMA at start should swap past the next consonant."""
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    # input: [RA=200, VIRAMA=201, CONS=50] → adjusted: [50, 200, 201]
    assert worker.apply_transforms([200, 201, 50]) == [50, 200, 201]


def test_reph_followed_by_aa_matra() -> None:
    """When AA-matra follows the consonant, reph moves past the matra too."""
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    # input: [RA, VIRAMA, CONS, AA-matra]
    # → [CONS, AA-matra, RA, VIRAMA] (matra is "before reph")
    result = worker.apply_transforms([200, 201, 50, 202])
    assert result == [50, 202, 200, 201]


def test_empty_input() -> None:
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    assert worker.apply_transforms([]) == []


def test_gsub_feature_applied() -> None:
    gd = GsubData(language="DEVANAGARI", feature_list={"akhn": {(80, 81): (777,)}})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    assert worker.apply_transforms([80, 81]) == [777]


def test_rkrf_synthesized_from_vatu_when_rkrf_absent() -> None:
    """When ``rkrf`` is missing but ``vatu`` is present with a 2-element
    cluster, the worker should synthesize the rkrf substitution.

    The synthesized rkrf collapses the trailing RA+VIRAMA into the
    second glyph of the first ``vatu`` cluster."""
    gd = GsubData(
        language="DEVANAGARI",
        feature_list={"vatu": {(50, 999): (999,)}},
    )
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    # input: [CONS=50, VIRAMA=201, RA=200]
    # adjustRephPosition leaves this alone (not RA+VIRAMA-CONS form).
    # rkrf-from-vatu replaces virama-position with 999 and removes RA.
    result = worker.apply_transforms([50, 201, 200])
    assert 999 in result
