from __future__ import annotations

from functools import cmp_to_key

from pypdfbox.text import TextPosition, TextPositionComparator


def _make(**overrides) -> TextPosition:
    base: dict = {
        "text": "x",
        "x": 0.0,
        "y": 0.0,
        "font_size": 10.0,
        "width": 5.0,
    }
    base.update(overrides)
    return TextPosition(**base)


# ---------------------------------------------------------------------------
# Direction grouping
# ---------------------------------------------------------------------------


def test_lower_direction_sorts_first():
    a = _make(dir=0.0)
    b = _make(dir=90.0)
    cmp = TextPositionComparator()
    assert cmp.compare(a, b) == -1
    assert cmp.compare(b, a) == 1


def test_equal_direction_falls_through_to_xy():
    a = _make(dir=90.0, x=0.0, y=10.0)
    b = _make(dir=90.0, x=5.0, y=10.0)
    cmp = TextPositionComparator()
    # Same baseline → x-ordering. dir=90 means get_x_dir_adj returns y,
    # which is identical (10) for both runs, so x-tie -> result 0.
    assert cmp.compare(a, b) == 0


# ---------------------------------------------------------------------------
# Same-line tolerance: order by X
# ---------------------------------------------------------------------------


def test_same_line_orders_by_x_left_first():
    a = _make(x=10.0, y=100.0, width=5.0, font_size=10.0)
    b = _make(x=20.0, y=100.0, width=5.0, font_size=10.0)
    cmp = TextPositionComparator()
    assert cmp.compare(a, b) == -1
    assert cmp.compare(b, a) == 1


def test_same_line_tie_returns_zero():
    a = _make(x=10.0, y=100.0)
    b = _make(x=10.0, y=100.0)
    assert TextPositionComparator().compare(a, b) == 0


def test_y_within_tolerance_orders_by_x():
    # Y differs by < 0.1 → treated as same baseline.
    a = _make(x=10.0, y=100.05, font_size=10.0)
    b = _make(x=20.0, y=100.0, font_size=10.0)
    assert TextPositionComparator().compare(a, b) == -1


# ---------------------------------------------------------------------------
# Different lines: order by Y (top-to-bottom)
# ---------------------------------------------------------------------------


def test_different_lines_orders_by_y_top_first():
    # pypdfbox keeps Y in the PDF user-space (y-up) frame the rest of the
    # library emits — a *larger* Y is geometrically higher and reads
    # first (the comparator's coordinate-frame carve-out).
    a = _make(x=50.0, y=10.0, font_size=10.0)
    b = _make(x=10.0, y=200.0, font_size=10.0)
    cmp = TextPositionComparator()
    # No vertical overlap, y_diff > 0.1 → order by y. b.y > a.y → b first.
    assert cmp.compare(a, b) == 1
    assert cmp.compare(b, a) == -1


# ---------------------------------------------------------------------------
# Vertical overlap: order by X even when y_difference >= 0.1
# ---------------------------------------------------------------------------


def test_vertically_overlapping_runs_order_by_x():
    # Two glyphs that vertically overlap (one's bottom is inside the
    # other's vertical extent) should fall through to x-ordering even
    # if their bottom Y differs.
    a = _make(x=10.0, y=100.0, font_size=20.0)
    b = _make(x=20.0, y=105.0, font_size=20.0)
    cmp = TextPositionComparator()
    result = cmp.compare(a, b)
    # a.x < b.x → -1 (overlap branch picks x).
    assert result == -1


# ---------------------------------------------------------------------------
# Sortability via cmp_to_key
# ---------------------------------------------------------------------------


def test_cmp_to_key_sorts_in_reading_order():
    # Same line, descending X; sorting by comparator yields ascending X.
    p3 = _make(x=30.0, y=100.0)
    p1 = _make(x=10.0, y=100.0)
    p2 = _make(x=20.0, y=100.0)
    sorted_positions = sorted([p3, p1, p2], key=cmp_to_key(TextPositionComparator()))
    assert [p.get_x() for p in sorted_positions] == [10.0, 20.0, 30.0]


def test_cmp_to_key_groups_by_direction_first():
    # Mixed directions — direction wins over Y/X.
    a = _make(x=999.0, y=999.0, dir=0.0)
    b = _make(x=0.0, y=0.0, dir=90.0)
    sorted_positions = sorted([b, a], key=cmp_to_key(TextPositionComparator()))
    # dir=0.0 sorts before dir=90.0 regardless of coords.
    assert sorted_positions[0] is a
    assert sorted_positions[1] is b


def test_callable_form_matches_compare():
    cmp = TextPositionComparator()
    a = _make(x=1.0, y=10.0)
    b = _make(x=2.0, y=10.0)
    assert cmp(a, b) == cmp.compare(a, b)


# ---------------------------------------------------------------------------
# Stateless / shareable
# ---------------------------------------------------------------------------


def test_comparator_is_reusable_across_pages():
    cmp = TextPositionComparator()
    page1 = sorted(
        [_make(x=2.0, y=10.0), _make(x=1.0, y=10.0)],
        key=cmp_to_key(cmp),
    )
    page2 = sorted(
        [_make(x=20.0, y=50.0), _make(x=10.0, y=50.0)],
        key=cmp_to_key(cmp),
    )
    assert [p.get_x() for p in page1] == [1.0, 2.0]
    assert [p.get_x() for p in page2] == [10.0, 20.0]


def test_comparator_exported_from_text_package():
    from pypdfbox.text import TextPositionComparator as Comparator

    assert Comparator is TextPositionComparator
