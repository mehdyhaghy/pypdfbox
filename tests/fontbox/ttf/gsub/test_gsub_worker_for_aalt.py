"""Hand-written tests for :class:`GsubWorkerForAALT`.

Synthetic ``aalt`` (Access All Alternates) shaping fixtures — pypdfbox
does not bundle the ``FoglihtenNo07.otf`` font upstream uses
(non-Apache custom license). These exercise the same code paths
(missing feature, empty substitution map, single-glyph substitution,
many-glyph pass-through) through synthetic :class:`GsubData` inputs.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData
from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_aalt import GsubWorkerForAALT


def test_apply_transforms_no_aalt_feature() -> None:
    """Font has no ``aalt`` feature — input passes through unchanged."""
    gsub_data = GsubData(active_script_name="latn", feature_list={})
    worker = GsubWorkerForAALT(gsub_data)
    assert worker.apply_transforms([1, 2, 3]) == [1, 2, 3]


def test_apply_transforms_empty_substitution_map() -> None:
    """``aalt`` is supported but carries no substitutions — pass through."""
    gsub_data = GsubData(
        active_script_name="latn",
        feature_list={"aalt": {}},
    )
    worker = GsubWorkerForAALT(gsub_data)
    assert worker.apply_transforms([10, 20]) == [10, 20]


def test_apply_transforms_single_glyph_substitution() -> None:
    """A single-glyph ``aalt`` substitution rewrites the corresponding GIDs."""
    gsub_data = GsubData(
        active_script_name="latn",
        feature_list={"aalt": {(65,): (1139,), (66,): (1562,), (67,): (1477,)}},
    )
    worker = GsubWorkerForAALT(gsub_data)
    # 'Abc' → expected upstream-equivalent alt forms.
    assert worker.apply_transforms([65, 66, 67]) == [1139, 1562, 1477]


def test_apply_transforms_partial_match_preserves_unmatched() -> None:
    """Glyphs not covered by the ``aalt`` map are left untouched."""
    gsub_data = GsubData(
        active_script_name="latn",
        feature_list={"aalt": {(65,): (200,)}},
    )
    worker = GsubWorkerForAALT(gsub_data)
    assert worker.apply_transforms([65, 99, 65]) == [200, 99, 200]


def test_apply_transforms_empty_input() -> None:
    gsub_data = GsubData(
        active_script_name="latn",
        feature_list={"aalt": {(65,): (200,)}},
    )
    worker = GsubWorkerForAALT(gsub_data)
    assert worker.apply_transforms([]) == []
