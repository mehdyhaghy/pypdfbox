"""Wave 1403 — branch round-out for :class:`GsubWorkerForDevanagari`.

Closes the partial arcs:

* ``[78,80]`` — ``vatu_feature is None`` False branch in
  :meth:`apply_transforms` (vatu supported but adapts to ``None``).
* ``[135,140]`` — ``ra_glyph == reph[0]`` False branch in
  :meth:`apply_rkrf_feature`.
* ``[137,140]`` — ``virama_glyph == reph[1]`` False branch in
  :meth:`apply_rkrf_feature`.
* ``[166,153]`` — ``matra_glyph in before_reph`` False branch in
  :meth:`adjust_reph_position`.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.gsub import GsubData, GsubWorkerForDevanagari


class _FakeCmap(CmapLookup):
    """Minimal :class:`CmapLookup` backed by an explicit code-point map."""

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


class _TwoElementClusterFeature:
    """Stand-in ``ScriptFeature`` with a valid 2-element cluster."""

    def get_name(self) -> str:
        return "rkrf-pair"

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        # (8, 9) -> rkrf_replacement = 9
        return {(8, 9)}


def test_apply_transforms_vatu_feature_adapts_to_none() -> None:
    """vatu supported but its payload is ``None`` → rkrf synthesis is
    skipped (``vatu_feature is None`` False arc, [78,80])."""
    gd = GsubData(language="DEVANAGARI", feature_list={"vatu": None})  # type: ignore[dict-item]
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    # No rkrf, vatu adapts to None — input passes through unchanged.
    assert worker.apply_transforms([50, 51, 52]) == [50, 51, 52]


def test_apply_rkrf_feature_no_reph_first_glyph_loops_on(  # noqa: D401
) -> None:
    """No RA (reph[0]) anywhere → every loop iteration takes the
    ``ra_glyph == reph[0]`` False arc ([135,140]) and the list is
    returned unchanged."""
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    original = [10, 20, 30, 40]
    out = worker.apply_rkrf_feature(_TwoElementClusterFeature(), original)
    assert out == original


def test_apply_rkrf_feature_reph_without_virama_loops_on() -> None:
    """RA present but the preceding glyph is not VIRAMA → the
    ``virama_glyph == reph[1]`` False arc ([137,140]) fires and the
    cluster is left intact."""
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    # index 3: ra=200==reph[0], but original[2]=30 != 201 -> False arc.
    original = [10, 20, 30, 200]
    out = worker.apply_rkrf_feature(_TwoElementClusterFeature(), original)
    assert out == original


def test_adjust_reph_position_reph_with_non_matra_tail() -> None:
    """A RA+VIRAMA cluster whose index+3 glyph is NOT a before-reph
    matra takes the ``matra_glyph in before_reph`` False arc ([166,153]).

    Input ``[RA=200, VIRAMA=201, CONS=50, X=60]`` — index 0 matches the
    reph cluster; the trailing glyph (60) is not a before-reph matra, so
    only the basic 3-glyph reorder happens, no matra drag.
    """
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    out = worker.adjust_reph_position([200, 201, 50, 60])
    # Basic reorder: consonant moves to front, RA+VIRAMA after it.
    assert out == [50, 200, 201, 60]
