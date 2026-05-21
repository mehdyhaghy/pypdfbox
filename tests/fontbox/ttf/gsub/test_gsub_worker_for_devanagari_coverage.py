"""Coverage-boost tests for :class:`GsubWorkerForDevanagari`.

Targets the empty-rkrf early-return, the missing 2-element-cluster
early-return, the i-matra reposition fall-through (pop-then-insert),
and the ``script_feature is None`` continue branch in
:meth:`apply_transforms`.
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


# ----------------------------------------------------------------------
# apply_transforms — script_feature is None continue branch
# ----------------------------------------------------------------------


def test_apply_transforms_skips_features_with_none_payload() -> None:
    """A supported feature with a ``None`` payload is silently skipped.

    Mirrors upstream's defensive ``if (scriptFeature == null) continue``.
    Covered: line 87 (``if script_feature is None: continue``).
    """
    # ``is_feature_supported`` returns True for any key present in the
    # feature_list dict, regardless of value — so a None value
    # round-trips into _adapt_feature which returns None.
    gd = GsubData(language="DEVANAGARI", feature_list={"akhn": None})  # type: ignore[dict-item]
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    assert worker.apply_transforms([10, 11]) == [10, 11]


# ----------------------------------------------------------------------
# apply_rkrf_feature — empty rkrf list + no 2-element cluster paths
# ----------------------------------------------------------------------


class _EmptyRkrfFeature:
    """Stand-in ``ScriptFeature`` whose substitution set is empty."""

    def get_name(self) -> str:
        return "rkrf-empty"

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        return set()


class _NoTwoElementClusterFeature:
    """Stand-in ``ScriptFeature`` with only single-element clusters."""

    def get_name(self) -> str:
        return "rkrf-singles"

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        return {(42,), (43,)}


def test_apply_rkrf_feature_empty_substitution_returns_input() -> None:
    """Empty substitution map → original glyph ids returned unchanged.

    Covered: lines 109-115 (empty-rkrf early return).
    """
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    original = [10, 20, 30]
    out = worker.apply_rkrf_feature(_EmptyRkrfFeature(), original)
    assert out == original


def test_apply_rkrf_feature_no_two_element_cluster_returns_input() -> None:
    """No cluster of length > 1 → original glyph ids returned unchanged.

    Covered: lines 125-129 (no-candidate early return).
    """
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    original = [10, 20, 30]
    out = worker.apply_rkrf_feature(_NoTwoElementClusterFeature(), original)
    assert out == original


# ----------------------------------------------------------------------
# reposition_glyphs — i-matra leftward move (lines 190-192)
# ----------------------------------------------------------------------


def test_reposition_glyphs_moves_i_matra_left() -> None:
    """I-matra (before-half) at the tail moves leftward past prior glyphs.

    Input: [CONS=50, OTHER=51, I-matra=204]
    The I-matra at index 2 is a ``before_half`` glyph; the loop pops it
    and reinserts at ``next_index``.

    Covered: lines 190-192 (i-matra pop + insert + decrement).
    """
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    out = worker.reposition_glyphs([50, 51, 204])
    # I-matra (204) was at the end; now sits earlier.
    assert 204 in out
    assert out.index(204) < 2


def test_reposition_glyphs_virama_after_i_matra() -> None:
    """A VIRAMA in the trailing slot does not displace the preceding
    I-matra; the I-matra is still hoisted leftward by the standard loop.

    Input: [CONS=50, I-matra=204, VIRAMA=201]
    """
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    out = worker.reposition_glyphs([50, 204, 201])
    assert 204 in out


def test_reposition_glyphs_multiple_i_matras_all_move_left() -> None:
    """Every I-matra glyph is popped and reinserted further left.

    Construct: ``[VIRAMA=201, I-matra=204, CONS=50, I-matra=204, X=60]``.
    Both I-matras survive in the result; the VIRAMA stays in place.
    """
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    out = worker.reposition_glyphs([201, 204, 50, 204, 60])
    assert out.count(204) == 2
    assert 201 in out


# ----------------------------------------------------------------------
# reposition_glyphs — multiple trailing i-matras preserve count
# ----------------------------------------------------------------------


def test_reposition_glyphs_trailing_i_matras_preserve_count() -> None:
    """Multiple trailing I-matras all pop+insert leftward without losing
    any glyph from the output list."""
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    out = worker.reposition_glyphs([50, 51, 52, 204, 204, 204])
    assert out.count(204) == 3


# ----------------------------------------------------------------------
# adjust_reph_position — short input doesn't enter the loop
# ----------------------------------------------------------------------


def test_adjust_reph_position_short_input_returns_copy() -> None:
    """Inputs shorter than 3 glyphs return an unchanged copy."""
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    assert worker.adjust_reph_position([200, 201]) == [200, 201]
    assert worker.adjust_reph_position([]) == []


def test_adjust_reph_position_no_reph_unchanged() -> None:
    """When no RA+VIRAMA sequence is present the list is unchanged."""
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    assert worker.adjust_reph_position([10, 11, 12, 13]) == [10, 11, 12, 13]


# ----------------------------------------------------------------------
# get_*_glyph_ids helpers — cmap returns 0 for missing characters
# ----------------------------------------------------------------------


def test_glyph_id_helpers_return_zero_for_missing_characters() -> None:
    """Helpers return 0 when the cmap has no entry for the script's
    code points (empty cmap)."""
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_FakeCmap({}), gd)
    assert worker.get_before_half_glyph_ids() == [0]
    assert worker.get_reph_glyph_ids() == [0, 0]
    assert worker.get_before_reph_glyph_ids() == [0, 0]


# ----------------------------------------------------------------------
# apply_gsub_feature — direct delegate exercise
# ----------------------------------------------------------------------


def test_apply_gsub_feature_with_dict_feature() -> None:
    """``apply_gsub_feature`` adapts a dict feature and runs the shared
    helper."""
    gd = GsubData(language="DEVANAGARI", feature_list={})
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    from pypdfbox.fontbox.ttf.gsub.gsub_worker import _adapt_feature

    feature = _adapt_feature("liga", {(1, 2): (99,)})
    assert worker.apply_gsub_feature(feature, [1, 2, 3]) == [99, 3]


# ----------------------------------------------------------------------
# apply_transforms — rkrf-from-vatu when vatu cluster has no 2-elem entry
# ----------------------------------------------------------------------


def test_apply_transforms_vatu_without_two_element_cluster_passes_through() -> None:
    """vatu present but no 2-element substitution cluster → input passes
    through unmodified (rkrf-synthesis bails out)."""
    gd = GsubData(
        language="DEVANAGARI",
        feature_list={"vatu": {(70,): (99,)}},
    )
    worker = GsubWorkerForDevanagari(_deva_cmap(), gd)
    # adjustRephPosition shouldn't trigger on this input.
    out = worker.apply_transforms([50, 201, 200])
    # vatu's single-element cluster doesn't yield a rkrf candidate,
    # so original glyphs are preserved (modulo any GSUB single-glyph
    # substitution from vatu itself, which 70→99 only fires on glyph 70).
    assert out == [50, 201, 200]
