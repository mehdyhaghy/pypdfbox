"""Wave 1403 — branch round-out for :class:`GsubWorkerForGujarati`.

Closes the partial arcs:

* ``[79,81]`` — ``vatu_feature is None`` False branch in
  :meth:`apply_transforms`.
* ``[134,139]`` — ``ra_glyph == reph[0]`` False branch in
  :meth:`apply_rkrf_feature`.
* ``[136,139]`` — ``virama_glyph == reph[1]`` False branch in
  :meth:`apply_rkrf_feature`.
* ``[162,149]`` — ``matra_glyph in before_reph`` False branch in
  :meth:`adjust_reph_position`.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.gsub import GsubData, GsubWorkerForGujarati


class _FakeCmap(CmapLookup):
    """Minimal :class:`CmapLookup` backed by an explicit code-point map."""

    def __init__(self, mapping: dict[int, int]) -> None:
        self._mapping = mapping

    def get_glyph_id(self, code_point_at: int) -> int:
        return self._mapping.get(code_point_at, 0)

    def get_char_codes(self, gid: int) -> list[int] | None:
        return [cp for cp, g in self._mapping.items() if g == gid] or None


def _guj_cmap() -> _FakeCmap:
    return _FakeCmap(
        {
            ord("ર"): 300,  # Gujarati RA (reph[0])
            ord("્"): 301,  # Gujarati VIRAMA (reph[1])
            ord("ા"): 302,  # AA-matra (before-reph)
            ord("ી"): 303,  # II-matra (before-reph)
            ord("િ"): 304,  # I-matra (before-half)
        }
    )


class _TwoElementClusterFeature:
    """Stand-in ``ScriptFeature`` with a valid 2-element cluster."""

    def get_name(self) -> str:
        return "rkrf-pair"

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        return {(8, 9)}


def test_apply_transforms_vatu_feature_adapts_to_none() -> None:
    """vatu supported but its payload is ``None`` → rkrf synthesis is
    skipped (``vatu_feature is None`` False arc, [79,81])."""
    gd = GsubData(language="GUJARATI", feature_list={"vatu": None})  # type: ignore[dict-item]
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    assert worker.apply_transforms([50, 51, 52]) == [50, 51, 52]


def test_apply_rkrf_feature_no_reph_first_glyph_loops_on() -> None:
    """No RA (reph[0]) anywhere → the ``ra_glyph == reph[0]`` False arc
    ([134,139]) fires on every iteration; list returned unchanged."""
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    original = [10, 20, 30, 40]
    out = worker.apply_rkrf_feature(_TwoElementClusterFeature(), original)
    assert out == original


def test_apply_rkrf_feature_reph_without_virama_loops_on() -> None:
    """RA present but its preceding glyph is not VIRAMA → the
    ``virama_glyph == reph[1]`` False arc ([136,139]) fires."""
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    # index 3: ra=300==reph[0], but original[2]=30 != 301 -> False arc.
    original = [10, 20, 30, 300]
    out = worker.apply_rkrf_feature(_TwoElementClusterFeature(), original)
    assert out == original


def test_adjust_reph_position_reph_with_non_matra_tail() -> None:
    """A RA+VIRAMA cluster whose index+3 glyph is NOT a before-reph
    matra takes the ``matra_glyph in before_reph`` False arc ([162,149]).
    """
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    out = worker.adjust_reph_position([300, 301, 50, 60])
    assert out == [50, 300, 301, 60]
