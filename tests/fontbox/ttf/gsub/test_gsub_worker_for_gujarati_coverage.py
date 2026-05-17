"""Coverage-boost tests for :class:`GsubWorkerForGujarati`.

Mirrors the Devanagari coverage suite — same branches, same shapes,
Gujarati code points. Targets: empty-rkrf early-return, the missing
2-element-cluster early-return, the i-matra reposition pop/insert path,
the matra-virama swap branch, and the ``script_feature is None``
continue branch in :meth:`apply_transforms`.
"""

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
            ord("ર"): 300,  # Gujarati RA (reph[0])
            ord("્"): 301,  # Gujarati VIRAMA (reph[1])
            ord("ા"): 302,  # AA-matra (before-reph)
            ord("ી"): 303,  # II-matra (before-reph)
            ord("િ"): 304,  # I-matra (before-half)
        }
    )


# ----------------------------------------------------------------------
# apply_transforms — script_feature is None continue branch (line 88)
# ----------------------------------------------------------------------


def test_apply_transforms_skips_features_with_none_payload() -> None:
    """Supported feature with a ``None`` payload is silently skipped.

    Covered: line 88 (``if script_feature is None: continue``).
    """
    gd = GsubData(language="GUJARATI", feature_list={"akhn": None})  # type: ignore[dict-item]
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    assert worker.apply_transforms([10, 11]) == [10, 11]


# ----------------------------------------------------------------------
# apply_rkrf_feature — empty + no 2-element cluster paths
# (lines 112-116, 124-128)
# ----------------------------------------------------------------------


class _EmptyRkrfFeature:
    def get_name(self) -> str:
        return "rkrf-empty"

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        return set()


class _NoTwoElementClusterFeature:
    def get_name(self) -> str:
        return "rkrf-singles"

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        return {(42,), (43,)}


def test_apply_rkrf_feature_empty_substitution_returns_input() -> None:
    """Empty substitution map → input returned unchanged (lines 112-116)."""
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    original = [10, 20, 30]
    out = worker.apply_rkrf_feature(_EmptyRkrfFeature(), original)
    assert out == original


def test_apply_rkrf_feature_no_two_element_cluster_returns_input() -> None:
    """No length>1 cluster → input returned unchanged (lines 124-128)."""
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    original = [10, 20, 30]
    out = worker.apply_rkrf_feature(_NoTwoElementClusterFeature(), original)
    assert out == original


# ----------------------------------------------------------------------
# reposition_glyphs — i-matra pop+insert path (lines 182-184)
# ----------------------------------------------------------------------


def test_reposition_glyphs_moves_i_matra_left() -> None:
    """I-matra (before-half) moves leftward (lines 182-184)."""
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    out = worker.reposition_glyphs([50, 51, 304])
    assert 304 in out
    assert out.index(304) < 2


def test_reposition_glyphs_virama_with_following_i_matra_swap() -> None:
    """The matra-virama swap branch (lines 194-196) fires when found_index
    lands on a VIRAMA whose ``found_index + 1`` neighbour is still an
    I-matra."""
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    out = worker.reposition_glyphs([301, 304, 50, 304, 60])
    assert out.count(304) == 2
    assert 301 in out


def test_reposition_glyphs_no_matras_unchanged() -> None:
    """Without any I-matras the list passes through unchanged."""
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    assert worker.reposition_glyphs([10, 11, 12]) == [10, 11, 12]


# ----------------------------------------------------------------------
# adjust_reph_position — short / negative cases
# ----------------------------------------------------------------------


def test_adjust_reph_position_short_input_returns_copy() -> None:
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    assert worker.adjust_reph_position([300, 301]) == [300, 301]
    assert worker.adjust_reph_position([]) == []


def test_adjust_reph_position_no_reph_unchanged() -> None:
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    assert worker.adjust_reph_position([10, 11, 12]) == [10, 11, 12]


# ----------------------------------------------------------------------
# Cmap-driven helpers — empty cmap returns zeroes
# ----------------------------------------------------------------------


def test_glyph_id_helpers_return_zero_for_missing_characters() -> None:
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_FakeCmap({}), gd)
    assert worker.get_before_half_glyph_ids() == [0]
    assert worker.get_reph_glyph_ids() == [0, 0]
    assert worker.get_before_reph_glyph_ids() == [0, 0]


# ----------------------------------------------------------------------
# apply_gsub_feature — delegate to shared helper
# ----------------------------------------------------------------------


def test_apply_gsub_feature_with_dict_feature() -> None:
    gd = GsubData(language="GUJARATI", feature_list={})
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    from pypdfbox.fontbox.ttf.gsub.gsub_worker import _adapt_feature

    feature = _adapt_feature("liga", {(1, 2): (99,)})
    assert worker.apply_gsub_feature(feature, [1, 2, 3]) == [99, 3]


def test_apply_transforms_vatu_without_two_element_cluster_passes_through() -> None:
    """vatu without a 2-element cluster → rkrf-synthesis bails out."""
    gd = GsubData(
        language="GUJARATI",
        feature_list={"vatu": {(70,): (99,)}},
    )
    worker = GsubWorkerForGujarati(_guj_cmap(), gd)
    out = worker.apply_transforms([50, 301, 300])
    assert out == [50, 301, 300]
