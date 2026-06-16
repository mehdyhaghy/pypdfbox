"""Wave 1567 — fuzz the PDFTextStripper text-ordering / separation logic.

This module hammers the reading-order sort and the line / word
separation heuristics that ``PDFTextStripper`` runs when stitching a
flat list of :class:`TextPosition` runs back into a single text stream:

  * ``set_sort_by_position`` on/off with out-of-order positions,
  * the ``_compare_reading_order`` comparator (the y-up-adapted port of
    upstream ``TextPositionComparator`` actually consulted on the
    extraction path) — same-baseline X ordering, vertical-overlap
    tie-break, mixed-direction grouping, the ``yDifference < .1``
    tolerance,
  * word-separator insertion thresholds (space-width-relative vs the
    coarse font-size fallback),
  * line-separator emission on Y jumps (the running-overlap model),
  * empty / single-glyph runs, very large coordinates, zero font size.

Positions are built both with the synthetic ``TextPosition`` API (to
exercise the comparator / separation helpers in isolation) and through
real content streams driven by ``get_text`` (the end-to-end path).

Expectations are pinned against upstream Apache PDFBox 3.0.7 semantics:
``TextPositionComparator`` groups by ``getDir()`` first, then orders a
shared-baseline pair left-to-right by X and a vertically-disjoint pair
top-to-bottom; the lite stripper carries Y in the PDF user-space (y-up)
frame, so "top first" means *larger* Y first.
"""
from __future__ import annotations

from functools import cmp_to_key

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, TextPosition


def _tp(text: str = "x", **kw: object) -> TextPosition:
    base: dict[str, object] = {
        "text": text,
        "x": 0.0,
        "y": 0.0,
        "font_size": 12.0,
        "width": 10.0,
    }
    base.update(kw)
    return TextPosition(**base)  # type: ignore[arg-type]


def _sorted(stripper: PDFTextStripper, positions: list[TextPosition]) -> list[str]:
    out = sorted(positions, key=cmp_to_key(stripper._compare_reading_order))
    return [p.text for p in out]


def _page(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# _compare_reading_order — same-baseline ordering by X
# ---------------------------------------------------------------------------


def test_same_baseline_orders_left_to_right() -> None:
    s = PDFTextStripper()
    left = _tp("L", x=100.0, y=500.0)
    right = _tp("R", x=300.0, y=500.0)
    assert s._compare_reading_order(left, right) < 0
    assert s._compare_reading_order(right, left) > 0


def test_same_baseline_within_tolerance_still_orders_by_x() -> None:
    """A sub-0.1 Y jitter must NOT reorder a visually shared line — the
    pair stays in left-to-right X order (the ``yDifference < .1``
    branch)."""
    s = PDFTextStripper()
    a = _tp("a", x=300.0, y=500.00)
    b = _tp("b", x=100.0, y=500.05)  # 0.05 jitter, higher x is to the right
    out = _sorted(s, [a, b])
    assert out == ["b", "a"]  # x 100 before x 300 despite a having smaller y


def test_y_tolerance_boundary_just_inside() -> None:
    s = PDFTextStripper()
    # Heights 0 so no vertical-overlap branch fires; only the .1 tolerance.
    a = _tp("a", x=200.0, y=500.0, height=0.0, font_size=0.0)
    b = _tp("b", x=100.0, y=500.099, height=0.0, font_size=0.0)
    # |dy| = 0.099 < 0.1 -> same line -> order by x (b first).
    assert _sorted(s, [a, b]) == ["b", "a"]


def test_y_tolerance_boundary_just_outside_orders_by_y() -> None:
    s = PDFTextStripper()
    # height/font_size 0 so the overlap branches cannot merge them.
    a = _tp("a", x=200.0, y=500.0, height=0.0, font_size=0.0)
    b = _tp("b", x=100.0, y=500.5, height=0.0, font_size=0.0)
    # |dy| = 0.5 > 0.1, disjoint -> larger y (b, higher) first.
    assert _sorted(s, [a, b]) == ["b", "a"]


# ---------------------------------------------------------------------------
# _compare_reading_order — vertically disjoint runs go top-to-bottom
# ---------------------------------------------------------------------------


def test_disjoint_lines_top_to_bottom() -> None:
    s = PDFTextStripper()
    top = _tp("T", x=100.0, y=700.0, height=0.0, font_size=0.0)
    bot = _tp("B", x=100.0, y=100.0, height=0.0, font_size=0.0)
    # y-up: larger y (700, higher) sorts first.
    assert s._compare_reading_order(top, bot) < 0
    assert _sorted(s, [bot, top]) == ["T", "B"]


def test_three_rows_two_columns_reading_order() -> None:
    s = PDFTextStripper()
    positions = [
        _tp("r1c2", x=300.0, y=700.0, height=0.0, font_size=0.0),
        _tp("r2c1", x=100.0, y=400.0, height=0.0, font_size=0.0),
        _tp("r1c1", x=100.0, y=700.0, height=0.0, font_size=0.0),
        _tp("r2c2", x=300.0, y=400.0, height=0.0, font_size=0.0),
    ]
    assert _sorted(s, positions) == ["r1c1", "r1c2", "r2c1", "r2c2"]


# ---------------------------------------------------------------------------
# _compare_reading_order — vertical-overlap merges differing baselines
# ---------------------------------------------------------------------------


def test_overlapping_extents_merge_to_one_line() -> None:
    """Two runs whose vertical glyph spans overlap (a tall run between
    two normal anchors) are treated as one line and ordered by X even
    though their baselines differ by more than the .1 tolerance."""
    s = PDFTextStripper()
    # tall run baseline 480, height 40 -> top edge 520
    tall = _tp("tall", x=300.0, y=480.0, height=40.0, font_size=40.0)
    # normal run baseline 500 sits inside [480, 520]; x smaller -> first.
    normal = _tp("norm", x=100.0, y=500.0, height=12.0, font_size=12.0)
    assert _sorted(s, [tall, normal]) == ["norm", "tall"]


def test_non_overlapping_extents_do_not_merge() -> None:
    s = PDFTextStripper()
    hi = _tp("hi", x=300.0, y=600.0, height=10.0, font_size=10.0)
    lo = _tp("lo", x=100.0, y=400.0, height=10.0, font_size=10.0)
    # spans [600,610] and [400,410] are disjoint -> top (hi) first by Y.
    assert _sorted(s, [lo, hi]) == ["hi", "lo"]


# ---------------------------------------------------------------------------
# _compare_reading_order — direction grouping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("d1", "d2", "expect_sign"),
    [
        (0.0, 90.0, -1),
        (90.0, 0.0, 1),
        (180.0, 270.0, -1),
        (270.0, 90.0, 1),
        (0.0, 0.0, 0),
    ],
    ids=["0<90", "90>0", "180<270", "270>90", "0==0-disjoint"],
)
def test_direction_grouping_precedes_position(
    d1: float, d2: float, expect_sign: int
) -> None:
    s = PDFTextStripper()
    # Give the two runs positions that would, on their own, sort the
    # other way — direction must win.
    a = _tp("a", x=900.0, y=100.0, dir=d1, height=0.0, font_size=0.0)
    b = _tp("b", x=0.0, y=900.0, dir=d2, height=0.0, font_size=0.0)
    cmp = s._compare_reading_order(a, b)
    if expect_sign < 0:
        assert cmp < 0
    elif expect_sign > 0:
        assert cmp > 0
    else:
        # Same direction, disjoint y -> ordered by y, not 0.
        assert cmp != 0


def test_mixed_direction_runs_emit_contiguously() -> None:
    s = PDFTextStripper()
    positions = [
        _tp("v1", x=10.0, y=10.0, dir=90.0, height=0.0, font_size=0.0),
        _tp("h1", x=10.0, y=700.0, dir=0.0, height=0.0, font_size=0.0),
        _tp("v2", x=10.0, y=20.0, dir=90.0, height=0.0, font_size=0.0),
        _tp("h2", x=10.0, y=600.0, dir=0.0, height=0.0, font_size=0.0),
    ]
    out = _sorted(s, positions)
    # All dir-0 runs come before all dir-90 runs (ascending direction).
    assert out.index("h1") < out.index("v1")
    assert out.index("h2") < out.index("v1")


# ---------------------------------------------------------------------------
# Comparator total-order sanity (cmp_to_key requires consistency)
# ---------------------------------------------------------------------------


def test_comparator_is_antisymmetric_on_random_grid() -> None:
    import random

    s = PDFTextStripper()
    rng = random.Random(1567)
    positions = [
        _tp(
            f"g{i}",
            x=rng.uniform(0, 600),
            y=rng.uniform(0, 800),
            height=rng.choice([0.0, 8.0, 24.0]),
            font_size=12.0,
            dir=rng.choice([0.0, 90.0, 180.0, 270.0]),
        )
        for i in range(40)
    ]
    for p in positions:
        for q in positions:
            c1 = s._compare_reading_order(p, q)
            c2 = s._compare_reading_order(q, p)
            # Antisymmetry: sign(cmp(p,q)) == -sign(cmp(q,p)).
            assert (c1 > 0) == (c2 < 0)
            assert (c1 < 0) == (c2 > 0)


def test_comparator_sort_is_deterministic_under_shuffle() -> None:
    import random

    s = PDFTextStripper()
    rng = random.Random(99)
    base = [
        _tp(f"g{i}", x=float(i % 5) * 100.0, y=float(i // 5) * 50.0,
            height=10.0, font_size=10.0)
        for i in range(20)
    ]
    reference = _sorted(s, base)
    for _ in range(8):
        shuffled = base[:]
        rng.shuffle(shuffled)
        assert _sorted(s, shuffled) == reference


# ---------------------------------------------------------------------------
# Empty / single-glyph / degenerate inputs
# ---------------------------------------------------------------------------


def test_empty_position_list_sorts_to_empty() -> None:
    s = PDFTextStripper()
    assert _sorted(s, []) == []


def test_single_glyph_run_is_identity_under_sort() -> None:
    s = PDFTextStripper()
    assert _sorted(s, [_tp("only", x=5.0, y=5.0)]) == ["only"]


def test_zero_font_size_zero_height_does_not_crash() -> None:
    s = PDFTextStripper()
    a = _tp("a", x=10.0, y=10.0, height=0.0, font_size=0.0)
    b = _tp("b", x=20.0, y=10.0, height=0.0, font_size=0.0)
    # Same baseline (dy=0 < .1) -> order by x.
    assert _sorted(s, [b, a]) == ["a", "b"]


def test_very_large_coordinates_order_consistently() -> None:
    s = PDFTextStripper()
    a = _tp("a", x=1e12, y=9.9e11, height=0.0, font_size=0.0)
    b = _tp("b", x=2e12, y=9.9e11 + 1.0, height=0.0, font_size=0.0)
    # dy = 1.0 > .1 -> disjoint -> larger y (b) first.
    assert _sorted(s, [a, b]) == ["b", "a"]


# ---------------------------------------------------------------------------
# _is_word_break — separator-insertion thresholds
# ---------------------------------------------------------------------------


def test_word_break_fires_on_wide_gap_fontsize_fallback() -> None:
    """Font-less run (font is None) uses the coarse font_size×1.5
    fallback."""
    s = PDFTextStripper()
    prev = _tp("A", x=0.0, y=100.0, width=10.0, font_size=12.0)
    # prev right edge = 10; gap threshold = 12*1.5 = 18.
    near = _tp("B", x=20.0, y=100.0, font_size=12.0)  # gap 10 < 18
    far = _tp("C", x=40.0, y=100.0, font_size=12.0)  # gap 30 > 18
    assert s._is_word_break(near, prev) is False
    assert s._is_word_break(far, prev) is True


def test_word_break_suppressed_when_prev_ends_with_separator() -> None:
    s = PDFTextStripper()
    prev = _tp("A ", x=0.0, y=100.0, width=10.0, font_size=12.0)
    far = _tp("B", x=999.0, y=100.0, font_size=12.0)
    # prev text ends with the word separator -> never insert another.
    assert s._is_word_break(far, prev) is False


def test_word_break_threshold_honours_custom_separator() -> None:
    s = PDFTextStripper()
    s.set_word_separator("|")
    # prev ends with space (not the configured separator) -> still breaks
    # on a wide gap; the suppression keys on the configured separator only.
    prev = _tp("A ", x=0.0, y=100.0, width=10.0, font_size=12.0)
    far = _tp("B", x=999.0, y=100.0, font_size=12.0)
    assert s._is_word_break(far, prev) is True


def test_word_break_no_width_uses_stretch_estimate() -> None:
    s = PDFTextStripper()
    # prev.width == 0 -> right edge = x + len(text)*font_size*0.5.
    prev = _tp("AB", x=0.0, y=100.0, width=0.0, font_size=12.0)
    # stretch = 2*12*0.5 = 12, right edge 12, threshold 18.
    near = _tp("C", x=25.0, y=100.0, font_size=12.0)  # gap 13 < 18
    far = _tp("D", x=40.0, y=100.0, font_size=12.0)  # gap 28 > 18
    assert s._is_word_break(near, prev) is False
    assert s._is_word_break(far, prev) is True


# ---------------------------------------------------------------------------
# _overlaps_line — line-break detection (the upright running-overlap model)
# ---------------------------------------------------------------------------


def test_overlaps_line_shared_baseline() -> None:
    # within(.1) clause.
    assert PDFTextStripper._overlaps_line(500.0, 12.0, 500.05, 12.0) is True


def test_overlaps_line_glyph_inside_line_span() -> None:
    # glyph baseline 505 within [500, 500+20].
    assert PDFTextStripper._overlaps_line(505.0, 12.0, 500.0, 20.0) is True


def test_overlaps_line_line_inside_glyph_span() -> None:
    # line baseline 500 within [495, 495+20].
    assert PDFTextStripper._overlaps_line(495.0, 20.0, 500.0, 8.0) is True


def test_overlaps_line_disjoint_returns_false() -> None:
    assert PDFTextStripper._overlaps_line(700.0, 10.0, 400.0, 10.0) is False


# ---------------------------------------------------------------------------
# End-to-end through get_text — sort on vs off
# ---------------------------------------------------------------------------


def test_sort_off_preserves_content_stream_order() -> None:
    doc = PDDocument()
    # Emit bottom line first, then top line, in stream order.
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 100 Tm (bottom) Tj "
            b"1 0 0 1 100 700 Tm (top) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_sort_by_position(False)
    out = s.get_text(doc)
    # Without sorting, stream order wins: bottom appears before top.
    assert out.index("bottom") < out.index("top")
    doc.close()


def test_sort_on_reorders_to_reading_order() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 100 Tm (bottom) Tj "
            b"1 0 0 1 100 700 Tm (top) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    # With sorting, the geometrically-higher run (top) comes first.
    assert out.index("top") < out.index("bottom")
    doc.close()


def test_sort_on_three_runs_out_of_order() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 300 Tm (middle) Tj "
            b"1 0 0 1 100 100 Tm (lower) Tj "
            b"1 0 0 1 100 700 Tm (upper) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    assert out.index("upper") < out.index("middle") < out.index("lower")
    doc.close()


def test_sort_on_same_line_orders_left_to_right() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 400 500 Tm (RIGHT) Tj "
            b"1 0 0 1 100 500 Tm (LEFT) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    assert out.index("LEFT") < out.index("RIGHT")
    doc.close()


def test_line_separator_between_distinct_rows() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (rowone) Tj "
            b"1 0 0 1 100 600 Tm (rowtwo) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    # A big vertical jump between rows yields a line separator between them.
    assert "rowone" in out
    assert "rowtwo" in out
    between = out[out.index("rowone") + len("rowone"): out.index("rowtwo")]
    assert s.get_line_separator() in between
    doc.close()


def test_custom_word_separator_is_used_on_wide_gap() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 500 Tm (AA) Tj "
            b"1 0 0 1 400 500 Tm (BB) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_word_separator("_")
    out = s.get_text(doc)
    assert "AA" in out
    assert "BB" in out
    # Same baseline, wide x gap -> a word separator (the custom "_").
    between = out[out.index("AA") + 2: out.index("BB")]
    assert "_" in between
    doc.close()


def test_empty_content_stream_yields_no_runs() -> None:
    doc = PDDocument()
    _page(doc, b"")
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    # Only structural separators (page end newline), no glyph text.
    assert out.strip() == ""
    doc.close()


def test_single_glyph_page_round_trips() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 1 0 0 1 100 500 Tm (Z) Tj ET")
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    assert "Z" in out
    doc.close()


def test_zero_font_size_run_does_not_crash_get_text() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 0 Tf 1 0 0 1 100 500 Tm (zero) Tj ET")
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    assert "zero" in out
    doc.close()


def test_very_large_translate_runs_still_extracted() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100000 500000 Tm (huge) Tj "
            b"1 0 0 1 100000 400000 Tm (next) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    assert out.index("huge") < out.index("next")
    doc.close()
