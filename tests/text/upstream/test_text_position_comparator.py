"""Upstream-equivalent parity tests for
``pypdfbox.text.TextPositionComparator``.

Upstream baseline: PDFBox 3.0.x.
Source: ``pdfbox/src/main/java/org/apache/pdfbox/text/TextPositionComparator.java``.

Upstream's ``TextPositionComparator implements
java.util.Comparator<TextPosition>`` is used by
``PDFTextStripper.writePage`` when ``sortByPosition`` is true. The
algorithm is:

1. Compare by ``getDir()``.
2. Within a direction, treat positions whose Y-difference is below 0.1
   *or* whose vertical extents overlap as same-line and order by X.
3. Otherwise, order by Y (top-to-bottom).

There is no upstream JUnit for this comparator — it's tested
transitively through the full ``TestTextStripper`` corpus diff. We pin
the per-axis behaviour directly so a future change to the tolerance or
overlap check is parity-checked.
"""
from __future__ import annotations

from functools import cmp_to_key

from pypdfbox.text import TextPosition, TextPositionComparator


def _pos(
    *,
    x: float = 0.0,
    y: float = 0.0,
    width: float = 10.0,
    font_size: float = 12.0,
    direction: float = 0.0,
) -> TextPosition:
    return TextPosition(
        text="x",
        x=x,
        y=y,
        font_size=font_size,
        width=width,
        dir=direction,
    )


def test_compare_returns_minus_one_when_direction_lower() -> None:
    """Step 1: different direction → strict ordering by dir."""
    cmp = TextPositionComparator()
    assert cmp.compare(_pos(direction=0), _pos(direction=90)) == -1


def test_compare_returns_plus_one_when_direction_higher() -> None:
    cmp = TextPositionComparator()
    assert cmp.compare(_pos(direction=180), _pos(direction=0)) == 1


def test_compare_returns_zero_for_two_identical_positions() -> None:
    """Step 3 with same x, same y — both Y-tolerance and X-equality
    paths converge on 0."""
    cmp = TextPositionComparator()
    a = _pos(x=10.0, y=20.0)
    b = _pos(x=10.0, y=20.0)
    assert cmp.compare(a, b) == 0


def test_same_line_y_within_tolerance_orders_by_x_ascending() -> None:
    """Step 2: Y-diff < 0.1 → order by directional X."""
    cmp = TextPositionComparator()
    a = _pos(x=5.0, y=100.0)
    b = _pos(x=10.0, y=100.05)  # within 0.1 tolerance
    assert cmp.compare(a, b) == -1
    assert cmp.compare(b, a) == 1


def test_same_line_y_equal_orders_by_x() -> None:
    cmp = TextPositionComparator()
    a = _pos(x=5.0, y=100.0)
    b = _pos(x=10.0, y=100.0)
    assert cmp.compare(a, b) == -1


def test_different_lines_with_no_overlap_order_by_y_top_first() -> None:
    """Step 3: Y-diff large, no vertical overlap → order by Y.

    pypdfbox carries Y in the PDF user-space (y-up) frame, so the
    *larger*-Y run is geometrically higher and reads first (the
    comparator's coordinate-frame carve-out)."""
    cmp = TextPositionComparator()
    a = _pos(x=5.0, y=50.0, font_size=10.0)  # y-up span 50..60
    b = _pos(x=5.0, y=100.0, font_size=10.0)  # y-up span 100..110 (higher)
    assert cmp.compare(a, b) == 1
    assert cmp.compare(b, a) == -1


def test_vertically_overlapping_positions_treated_as_same_line() -> None:
    """Step 2's vertical-overlap clause: a tall glyph that visually
    overlaps the next run's Y-extent is treated as same-line.
    """
    cmp = TextPositionComparator()
    # A: y=100, height 20 → top=80, bottom=100
    # B: y=110, height 20 → top=90, bottom=110
    # bottom-A (100) is between top-B (90) and bottom-B (110).
    a = _pos(x=5.0, y=100.0, font_size=20.0)
    b = _pos(x=10.0, y=110.0, font_size=20.0)
    assert cmp.compare(a, b) == -1


def test_cmp_to_key_sorts_list_in_reading_order() -> None:
    """Direct usage idiom: ``list.sort(key=cmp_to_key(comparator))``."""
    cmp = TextPositionComparator()
    positions = [
        _pos(x=20.0, y=100.0),
        _pos(x=5.0, y=200.0),
        _pos(x=5.0, y=100.0),
        _pos(x=20.0, y=200.0),
    ]
    positions.sort(key=cmp_to_key(cmp))
    coords = [(p.x, p.y) for p in positions]
    # y-up reading order: higher Y first (line at y=200); within each
    # line, x ascends.
    assert coords == [(5.0, 200.0), (20.0, 200.0), (5.0, 100.0), (20.0, 100.0)]


def test_call_alias_matches_compare_for_every_branch() -> None:
    """``cmp(a, b)`` (``__call__``) must equal ``cmp.compare(a, b)``."""
    cmp = TextPositionComparator()
    samples = [
        (_pos(x=0, y=0, direction=0), _pos(x=0, y=0, direction=90)),
        (_pos(x=0, y=100), _pos(x=10, y=100)),
        (_pos(x=0, y=100), _pos(x=0, y=200)),
        (_pos(x=10, y=100), _pos(x=10, y=100)),
    ]
    for a, b in samples:
        assert cmp(a, b) == cmp.compare(a, b)


def test_comparator_is_stateless_and_shareable() -> None:
    """Two comparators must produce identical ordering — no per-instance
    state."""
    cmp1 = TextPositionComparator()
    cmp2 = TextPositionComparator()
    a = _pos(x=10, y=100)
    b = _pos(x=20, y=200)
    assert cmp1.compare(a, b) == cmp2.compare(a, b)


def test_tolerance_constant_is_zero_point_one() -> None:
    """The 0.1 tolerance is part of the public contract — pin so a
    refactor doesn't silently raise it.
    """
    assert TextPositionComparator._Y_TOLERANCE == 0.1
