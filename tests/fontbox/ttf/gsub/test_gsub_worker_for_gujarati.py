"""Tests for :class:`GsubWorkerForGujarati`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.gsub import GsubData, GsubWorkerForGujarati


class _FakeCmap(CmapLookup):
    def __init__(self, mapping: dict[int, int]) -> None:
        self._mapping = mapping

    def get_glyph_id(self, code_point_at: int) -> int:
        return self._mapping.get(code_point_at, 0)

    def get_char_codes(self, gid: int) -> list[int] | None:
        return [cp for cp, g in self._mapping.items() if g == gid] or None


def _guj_cmap() -> _FakeCmap:
    return _FakeCmap(
        {
            ord("ર"): 300,  # Gujarati RA
            ord("્"): 301,  # Gujarati VIRAMA
            ord("ા"): 302,  # AA-matra (before-reph)
            ord("ી"): 303,  # II-matra (before-reph)
            ord("િ"): 304,  # I-matra (before-half)
        }
    )


def test_pass_through_basic_consonants() -> None:
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    assert worker.apply_transforms([10, 11, 12]) == [10, 11, 12]


def test_reph_position_adjusted() -> None:
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    # input: [RA, VIRAMA, CONS] → [CONS, RA, VIRAMA]
    assert worker.apply_transforms([300, 301, 50]) == [50, 300, 301]


def test_reph_followed_by_aa_matra() -> None:
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    assert worker.apply_transforms([300, 301, 50, 302]) == [50, 302, 300, 301]


def test_empty_input() -> None:
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    assert worker.apply_transforms([]) == []


def test_gsub_feature_applied() -> None:
    gd = GsubData(language="GUJARATI", feature_list={"akhn": {(80, 81): (777,)}})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    assert worker.apply_transforms([80, 81]) == [777]


def test_rkrf_synthesized_from_vatu() -> None:
    gd = GsubData(
        language="GUJARATI",
        feature_list={"vatu": {(50, 999): (999,)}},
    )
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    result = worker.apply_transforms([50, 301, 300])
    assert 999 in result
