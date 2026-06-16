"""Wave 1370 — TextPosition directional accessors + sort comparison.

Pins the direction-aware ``get_x_dir_adj`` / ``get_y_dir_adj`` /
``get_x_rot`` / ``get_y_lower_left_rot`` accessors against the same
sort key construction patterns used in the lite stripper's
``_format_positions`` (where ``sort_by_position=True`` builds a tuple
``(-y, x)``).

The :class:`TextPositionComparator` is exercised separately under
``test_text_position_comparator.py``; these tests focus on the raw
field-level outputs that feed both code paths.
"""
from __future__ import annotations

from functools import cmp_to_key

from pypdfbox.text import TextPosition, TextPositionComparator


def _tp(text: str = "x", **kw) -> TextPosition:
    base = {
        "text": text,
        "x": 0.0,
        "y": 0.0,
        "font_size": 12.0,
        "width": 10.0,
    }
    base.update(kw)
    return TextPosition(**base)


# ---------------------------------------------------------------------------
# Directional X/Y mirror the un-rotated coordinates for dir=0
# ---------------------------------------------------------------------------


def test_x_dir_adj_equals_x_at_dir_zero() -> None:
    tp = _tp(x=42.0, dir=0.0)
    assert tp.get_x_dir_adj() == 42.0
    assert tp.get_x_directional_adj() == 42.0


def test_y_dir_adj_equals_y_at_dir_zero() -> None:
    tp = _tp(y=42.0, dir=0.0)
    assert tp.get_y_dir_adj() == 42.0
    assert tp.get_y_directional_adj() == 42.0


# ---------------------------------------------------------------------------
# Directional X/Y rotate by 90/180/270 against page extents
# ---------------------------------------------------------------------------


def test_dir_90_swaps_x_and_y_axes() -> None:
    """At ``dir=90`` the run is rotated counter-clockwise — directional
    X reads from the run's Y, and directional Y from the page-width
    minus X."""
    tp = _tp(x=100.0, y=50.0, dir=90.0, page_width=500.0)
    assert tp.get_x_dir_adj() == 50.0
    assert tp.get_y_dir_adj() == 400.0  # 500 - 100


def test_dir_180_flips_x_around_page_width() -> None:
    tp = _tp(x=100.0, y=50.0, dir=180.0, page_width=612.0, page_height=792.0)
    assert tp.get_x_dir_adj() == 512.0  # 612 - 100
    assert tp.get_y_dir_adj() == 742.0  # 792 - 50


def test_dir_270_flips_y_around_page_height() -> None:
    tp = _tp(x=100.0, y=50.0, dir=270.0, page_width=612.0, page_height=792.0)
    assert tp.get_x_dir_adj() == 742.0  # 792 - 50
    assert tp.get_y_dir_adj() == 100.0  # x


# ---------------------------------------------------------------------------
# Sort by directional y matches sort by raw y at dir=0 (regression guard)
# ---------------------------------------------------------------------------


def test_sort_by_directional_y_matches_raw_y_for_dir_zero() -> None:
    positions = [
        _tp("a", y=100.0),
        _tp("b", y=300.0),
        _tp("c", y=200.0),
    ]
    # Sort by directional y (ascending).
    sorted_dir = sorted(positions, key=lambda p: p.get_y_dir_adj())
    sorted_raw = sorted(positions, key=lambda p: p.y)
    assert [p.text for p in sorted_dir] == [p.text for p in sorted_raw]


def test_sort_by_neg_directional_y_then_x_matches_stripper_keying() -> None:
    """The stripper uses ``key=lambda p: (-p.y, p.x)`` for sort-by-position.
    Confirm the same composite key reads as expected on hand-built data."""
    positions = [
        _tp("low-left", x=100.0, y=100.0),
        _tp("low-right", x=400.0, y=100.0),
        _tp("high-left", x=100.0, y=700.0),
        _tp("high-right", x=400.0, y=700.0),
    ]
    s = sorted(positions, key=lambda p: (-p.y, p.x))
    assert [p.text for p in s] == [
        "high-left",
        "high-right",
        "low-left",
        "low-right",
    ]


# ---------------------------------------------------------------------------
# TextPositionComparator orders by direction first, then by Y, then X
# ---------------------------------------------------------------------------


def test_comparator_groups_by_direction_first() -> None:
    """Two positions with different ``dir`` values get partitioned by
    direction regardless of which has the larger directional X/Y."""
    pos_dir0 = _tp("a", dir=0.0, y=100.0, x=900.0)
    pos_dir90 = _tp("b", dir=90.0, y=100.0, x=0.0)
    cmp = TextPositionComparator()
    # dir 0 < dir 90 -> pos_dir0 sorts first.
    assert cmp(pos_dir0, pos_dir90) < 0
    assert cmp(pos_dir90, pos_dir0) > 0


def test_comparator_sorts_same_line_by_x() -> None:
    """When two positions share a baseline (Y within tolerance) the
    comparator falls back to ascending X."""
    left = _tp("L", x=100.0, y=700.0)
    right = _tp("R", x=300.0, y=700.0)
    cmp = TextPositionComparator()
    assert cmp(left, right) < 0
    assert cmp(right, left) > 0


def test_comparator_sorts_different_lines_by_y() -> None:
    """Different Y (outside the tolerance window) falls back to
    top-to-bottom ordering by directional Y.

    pypdfbox carries Y in the PDF user-space (y-up) frame the rest of
    the library emits — a *larger* Y is geometrically higher and sorts
    first (see the comparator's coordinate-frame note)."""
    top = _tp("T", x=100.0, y=500.0)
    bot = _tp("B", x=100.0, y=100.0)
    cmp = TextPositionComparator()
    # y-up: the larger-Y run (top) is higher on the page, sorts first.
    assert cmp(top, bot) < 0


def test_comparator_returns_zero_for_equal_positions() -> None:
    a = _tp("a", x=10.0, y=10.0)
    b = _tp("a", x=10.0, y=10.0)
    cmp = TextPositionComparator()
    assert cmp(a, b) == 0


def test_comparator_usable_as_cmp_to_key() -> None:
    """Comparator must be wrap-able with :func:`functools.cmp_to_key` —
    the canonical Java->Python idiom."""
    # y-up frame: the larger-Y row is geometrically higher (the "top"
    # row), so it reads first.
    positions = [
        _tp("right-bottom", x=300.0, y=100.0),
        _tp("left-top", x=100.0, y=700.0),
        _tp("left-bottom", x=100.0, y=100.0),
        _tp("right-top", x=300.0, y=700.0),
    ]
    s = sorted(positions, key=cmp_to_key(TextPositionComparator()))
    # Top row first (larger y -> higher in the y-up frame), then bottom.
    # Within row, ascending x.
    texts = [p.text for p in s]
    assert texts.index("left-top") < texts.index("right-top")
    assert texts.index("right-top") < texts.index("left-bottom")
    assert texts.index("left-bottom") < texts.index("right-bottom")


# ---------------------------------------------------------------------------
# Rotation helpers (get_x_rot / get_y_lower_left_rot) feed into composite
# sort keys when rotation is explicit
# ---------------------------------------------------------------------------


def test_get_x_rot_zero_returns_x() -> None:
    tp = _tp(x=42.0)
    assert tp.get_x_rot(0.0) == 42.0


def test_get_x_rot_180_uses_page_width_minus_x() -> None:
    tp = _tp(x=100.0, page_width=500.0)
    assert tp.get_x_rot(180.0) == 400.0


def test_get_y_lower_left_rot_180_uses_page_height_minus_y() -> None:
    tp = _tp(y=100.0, page_height=800.0)
    assert tp.get_y_lower_left_rot(180.0) == 700.0


def test_rotation_helpers_unsupported_angle_returns_zero() -> None:
    """Upstream returns ``0`` for any rotation that isn't 0/90/180/270.
    Pin the same behaviour."""
    tp = _tp(x=42.0, y=42.0)
    assert tp.get_x_rot(33.3) == 0.0
    assert tp.get_y_lower_left_rot(33.3) == 0.0


# ---------------------------------------------------------------------------
# Composite sort key built from rotation helpers vs directional accessors
# ---------------------------------------------------------------------------


def test_composite_sort_with_rotation_helpers_is_stable() -> None:
    """Two positions sharing the same rotation-projected X and Y must
    sort stably (Python's ``sorted`` is guaranteed stable)."""
    a = _tp("a", x=100.0, y=100.0, page_width=500.0)
    b = _tp("b", x=100.0, y=100.0, page_width=500.0)
    sorted_list = sorted(
        [a, b], key=lambda p: (p.get_x_rot(180.0), p.get_y_lower_left_rot(180.0))
    )
    # Equal keys: original order preserved (a before b).
    assert [p.text for p in sorted_list] == ["a", "b"]


# ---------------------------------------------------------------------------
# Width accessors agree across rotation toggles in the lite model
# ---------------------------------------------------------------------------


def test_width_rot_is_invariant_across_supported_angles() -> None:
    """The lite ``get_width_rot`` is direction-agnostic — width is
    stored along the run's text-direction axis. Confirm all four
    supported angles return the same value (upstream-divergence
    documented in the class docstring)."""
    tp = _tp(width=42.5)
    assert tp.get_width_rot(0.0) == 42.5
    assert tp.get_width_rot(90.0) == 42.5
    assert tp.get_width_rot(180.0) == 42.5
    assert tp.get_width_rot(270.0) == 42.5
