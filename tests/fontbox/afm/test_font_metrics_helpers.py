"""Hand-written tests for FontMetrics helper accessors.

Covers the typed lookup ``get_char_metric``, the ``has_*`` predicate
helpers (``has_char_metric`` / ``has_font_b_box`` / ``has_v_vector`` /
``has_char_width``), and the aggregate ``get_total_kern_pair_count``.

These do not exist upstream; they're convenience helpers around the
internal name->metric map and the optional-field state. The tests pin
the None-tolerance semantics that upstream's getter pattern leaves
implicit.
"""
from __future__ import annotations

from pypdfbox.fontbox.afm import CharMetric, FontMetrics, KernPair
from pypdfbox.fontbox.ttf.glyph_data import BoundingBox

# ---------------------------------------------------------------------------
# get_char_metric / has_char_metric
# ---------------------------------------------------------------------------


def _metric(name: str, wx: float = 0.0) -> CharMetric:
    cm = CharMetric()
    cm.set_name(name)
    cm.set_wx(wx)
    return cm


def test_get_char_metric_returns_added_entry() -> None:
    fm = FontMetrics()
    a = _metric("A", 500)
    fm.add_char_metric(a)
    assert fm.get_char_metric("A") is a


def test_get_char_metric_returns_none_for_unknown_name() -> None:
    fm = FontMetrics()
    fm.add_char_metric(_metric("A", 500))
    assert fm.get_char_metric("Zzz") is None


def test_get_char_metric_none_name_returns_none() -> None:
    fm = FontMetrics()
    fm.add_char_metric(_metric("A", 500))
    assert fm.get_char_metric(None) is None  # type: ignore[arg-type]


def test_get_char_metric_after_set_char_metrics_replaces_lookup() -> None:
    fm = FontMetrics()
    fm.add_char_metric(_metric("A", 500))
    fm.set_char_metrics([_metric("B", 600)])
    assert fm.get_char_metric("A") is None
    b = fm.get_char_metric("B")
    assert b is not None
    assert b.get_wx() == 600.0


def test_has_char_metric_present() -> None:
    fm = FontMetrics()
    fm.add_char_metric(_metric("A", 500))
    assert fm.has_char_metric("A") is True


def test_has_char_metric_absent() -> None:
    fm = FontMetrics()
    fm.add_char_metric(_metric("A", 500))
    assert fm.has_char_metric("B") is False


def test_has_char_metric_none_name_is_false() -> None:
    fm = FontMetrics()
    fm.add_char_metric(_metric("A", 500))
    assert fm.has_char_metric(None) is False  # type: ignore[arg-type]


def test_add_char_metric_with_empty_name_skips_lookup_entry() -> None:
    # Edge case: a CharMetric without an N directive shouldn't pollute the
    # map. The constructor leaves the name as the empty string.
    fm = FontMetrics()
    nameless = CharMetric()
    nameless.set_wx(123)
    fm.add_char_metric(nameless)
    # Stored in the ordered list...
    assert fm.get_char_metrics() == [nameless]
    # ...but the lookup map stays empty.
    assert fm.get_char_metric("") is None
    assert fm.has_char_metric("") is False


# ---------------------------------------------------------------------------
# Optional-field predicate helpers
# ---------------------------------------------------------------------------


def test_has_font_b_box_default_false() -> None:
    fm = FontMetrics()
    assert fm.has_font_b_box() is False


def test_has_font_b_box_true_after_set() -> None:
    fm = FontMetrics()
    fm.set_font_b_box(BoundingBox(0, 0, 100, 100))
    assert fm.has_font_b_box() is True


def test_has_font_b_box_false_after_clear() -> None:
    fm = FontMetrics()
    fm.set_font_b_box(BoundingBox(0, 0, 100, 100))
    fm.set_font_b_box(None)
    assert fm.has_font_b_box() is False


def test_has_v_vector_default_false() -> None:
    fm = FontMetrics()
    assert fm.has_v_vector() is False


def test_has_v_vector_after_tuple_set() -> None:
    fm = FontMetrics()
    fm.set_v_vector((100, 200))
    assert fm.has_v_vector() is True


def test_has_v_vector_after_list_set() -> None:
    fm = FontMetrics()
    fm.set_v_vector([100, 200])
    assert fm.has_v_vector() is True


def test_has_v_vector_false_after_clear() -> None:
    fm = FontMetrics()
    fm.set_v_vector((10, 20))
    fm.set_v_vector(None)
    assert fm.has_v_vector() is False


def test_has_char_width_default_false() -> None:
    fm = FontMetrics()
    assert fm.has_char_width() is False


def test_has_char_width_true_after_set() -> None:
    fm = FontMetrics()
    fm.set_char_width((600, 0))
    assert fm.has_char_width() is True


def test_has_char_width_false_after_clear() -> None:
    fm = FontMetrics()
    fm.set_char_width([600, 0])
    fm.set_char_width(None)
    assert fm.has_char_width() is False


# ---------------------------------------------------------------------------
# get_total_kern_pair_count
# ---------------------------------------------------------------------------


def test_total_kern_pair_count_zero_default() -> None:
    fm = FontMetrics()
    assert fm.get_total_kern_pair_count() == 0


def test_total_kern_pair_count_sums_three_lists() -> None:
    fm = FontMetrics()
    fm.add_kern_pair(KernPair("A", "B", -10, 0))
    fm.add_kern_pair(KernPair("C", "D", -20, 0))
    fm.add_kern_pair0(KernPair("E", "F", -30, 0))
    fm.add_kern_pair1(KernPair("G", "H", -40, 0))
    fm.add_kern_pair1(KernPair("I", "J", -50, 0))
    assert fm.get_total_kern_pair_count() == 5


def test_total_kern_pair_count_only_kern_pairs0() -> None:
    fm = FontMetrics()
    fm.add_kern_pair0(KernPair("A", "B", -1, 0))
    fm.add_kern_pair0(KernPair("C", "D", -2, 0))
    assert fm.get_total_kern_pair_count() == 2


def test_total_kern_pair_count_independent_of_track_kern() -> None:
    # Track kern entries shouldn't be counted as kern pairs.
    from pypdfbox.fontbox.afm import TrackKern

    fm = FontMetrics()
    fm.add_track_kern(TrackKern(0, 8, -1, 32, -3))
    fm.add_kern_pair(KernPair("A", "B", -10, 0))
    assert fm.get_total_kern_pair_count() == 1
