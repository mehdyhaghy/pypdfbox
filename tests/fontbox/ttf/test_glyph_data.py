"""Tests for :class:`pypdfbox.fontbox.ttf.GlyphData`.

Loads LiberationSans-Regular and exercises the bbox / contour-count /
path accessors against well-known glyphs (``.notdef`` at gid 0 plus a
couple of real outlines).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import (
    BoundingBox,
    GlyfDescript,
    GlyphData,
    GlyphDescription,
    TrueTypeFont,
)

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


# ---------- BoundingBox basics --------------------------------------------


def test_bounding_box_default_is_zero() -> None:
    b = BoundingBox()
    assert b.get_lower_left_x() == 0.0
    assert b.get_lower_left_y() == 0.0
    assert b.get_upper_right_x() == 0.0
    assert b.get_upper_right_y() == 0.0
    assert b.get_width() == 0.0
    assert b.get_height() == 0.0


def test_bounding_box_constructor() -> None:
    b = BoundingBox(1, 2, 5, 9)
    assert b.get_lower_left_x() == 1.0
    assert b.get_lower_left_y() == 2.0
    assert b.get_upper_right_x() == 5.0
    assert b.get_upper_right_y() == 9.0
    assert b.get_width() == 4.0
    assert b.get_height() == 7.0
    assert b.as_tuple() == (1.0, 2.0, 5.0, 9.0)


def test_bounding_box_setters() -> None:
    b = BoundingBox()
    b.set_lower_left_x(1.5)
    b.set_lower_left_y(2.5)
    b.set_upper_right_x(3.5)
    b.set_upper_right_y(4.5)
    assert b.as_tuple() == (1.5, 2.5, 3.5, 4.5)


def test_bounding_box_contains_inside() -> None:
    b = BoundingBox(0, 0, 10, 10)
    assert b.contains(5, 5)


def test_bounding_box_contains_on_edge() -> None:
    # Upstream contract: edge points are inside.
    b = BoundingBox(0, 0, 10, 10)
    assert b.contains(0, 0)
    assert b.contains(10, 10)
    assert b.contains(0, 5)
    assert b.contains(5, 10)


def test_bounding_box_contains_outside() -> None:
    b = BoundingBox(0, 0, 10, 10)
    assert not b.contains(-1, 5)
    assert not b.contains(11, 5)
    assert not b.contains(5, -1)
    assert not b.contains(5, 11)


def test_bounding_box_str_matches_upstream() -> None:
    # Upstream toString: "[ll_x,ll_y,ur_x,ur_y]" with no spaces.
    b = BoundingBox(1.0, 2.0, 3.0, 4.0)
    assert str(b) == "[1.0,2.0,3.0,4.0]"


def test_bounding_box_from_numbers() -> None:
    b = BoundingBox.from_numbers([1, 2, 5, 9])
    assert b.as_tuple() == (1.0, 2.0, 5.0, 9.0)


def test_bounding_box_from_numbers_wrong_arity() -> None:
    with pytest.raises(ValueError):
        BoundingBox.from_numbers([1, 2, 3])
    with pytest.raises(ValueError):
        BoundingBox.from_numbers([1, 2, 3, 4, 5])


# ---------- empty GlyphData ------------------------------------------------


def test_empty_glyph_data_has_zero_bbox() -> None:
    g = GlyphData()
    bb = g.get_bounding_box()
    assert isinstance(bb, BoundingBox)
    assert bb.as_tuple() == (0.0, 0.0, 0.0, 0.0)
    assert g.get_number_of_contours() == 0


def test_empty_glyph_data_path_is_empty() -> None:
    g = GlyphData()
    pen = g.get_path()
    # RecordingPen.value is the list of recorded operations.
    assert pen.value == []


# ---------- GlyphData via real font ----------------------------------------


def test_notdef_has_a_bounding_box(liberation_sans: TrueTypeFont) -> None:
    g = liberation_sans.get_glyph(0)
    assert g is not None
    bb = g.get_bounding_box()
    assert isinstance(bb, BoundingBox)
    # LiberationSans-Regular .notdef glyph: (205, 0) -> (1330, 1409).
    assert bb.as_tuple() == (205.0, 0.0, 1330.0, 1409.0)


def test_notdef_contour_count_matches_glyf(liberation_sans: TrueTypeFont) -> None:
    g = liberation_sans.get_glyph(0)
    assert g is not None
    # .notdef in Liberation Sans is the classic two-contour rectangle.
    assert g.get_number_of_contours() == 2


def test_notdef_min_max_accessors_match_bbox(
    liberation_sans: TrueTypeFont,
) -> None:
    g = liberation_sans.get_glyph(0)
    assert g is not None
    assert g.get_x_minimum() == 205
    assert g.get_y_minimum() == 0
    assert g.get_x_maximum() == 1330
    assert g.get_y_maximum() == 1409


def test_glyph_path_records_outline(liberation_sans: TrueTypeFont) -> None:
    g = liberation_sans.get_glyph(0)
    assert g is not None
    pen = g.get_path()
    # An outlined glyph must produce at least one moveTo and one closePath.
    ops = [op for op, _args in pen.value]
    assert "moveTo" in ops
    assert "closePath" in ops


def test_letter_a_has_outline(liberation_sans: TrueTypeFont) -> None:
    cmap = liberation_sans.get_unicode_cmap_subtable()
    assert cmap is not None
    gid = cmap.get_glyph_id(ord("A"))
    assert gid is not None
    assert gid > 0
    g = liberation_sans.get_glyph(gid)
    assert g is not None
    bb = g.get_bounding_box()
    # Liberation Sans 'A' bbox.
    assert bb.as_tuple() == (4.0, 0.0, 1362.0, 1409.0)
    pen = g.get_path()
    assert pen.value, "letter 'A' must have a non-empty path"


# ---------- GlyfDescript flag constants -----------------------------------


def test_glyf_descript_flag_constants() -> None:
    # Mirrors the public bit values from upstream GlyfDescript.
    assert GlyfDescript.ON_CURVE == 0x01
    assert GlyfDescript.X_SHORT_VECTOR == 0x02
    assert GlyfDescript.Y_SHORT_VECTOR == 0x04
    assert GlyfDescript.REPEAT == 0x08
    assert GlyfDescript.X_DUAL == 0x10
    assert GlyfDescript.Y_DUAL == 0x20


# ---------- GlyphDescription via empty GlyphData --------------------------


def test_empty_glyph_data_description_is_empty() -> None:
    g = GlyphData()
    desc = g.get_description()
    assert isinstance(desc, GlyphDescription)
    assert desc.is_composite() is False
    assert desc.get_contour_count() == 0
    assert desc.get_point_count() == 0
    # resolve() on an empty description must not raise.
    desc.resolve()


# ---------- GlyphDescription via real font --------------------------------


def test_notdef_description_matches_glyf(liberation_sans: TrueTypeFont) -> None:
    g = liberation_sans.get_glyph(0)
    assert g is not None
    desc = g.get_description()
    assert isinstance(desc, GlyphDescription)
    assert desc.is_composite() is False
    # .notdef in Liberation Sans: two contours, eight points (4-pt outer
    # + 4-pt inner rectangle).
    assert desc.get_contour_count() == 2
    assert desc.get_point_count() == 8
    # First contour ends before the second; both endpoint indices are
    # within range and strictly increasing.
    e0 = desc.get_end_pt_of_contours(0)
    e1 = desc.get_end_pt_of_contours(1)
    assert 0 <= e0 < e1
    assert e1 == desc.get_point_count() - 1


def test_notdef_description_coordinates_lie_inside_bbox(
    liberation_sans: TrueTypeFont,
) -> None:
    g = liberation_sans.get_glyph(0)
    assert g is not None
    desc = g.get_description()
    bb = g.get_bounding_box()
    for i in range(desc.get_point_count()):
        x = desc.get_x_coordinate(i)
        y = desc.get_y_coordinate(i)
        assert bb.contains(x, y), f"point ({x},{y}) outside bbox {bb}"


def test_notdef_description_flags_are_on_curve(
    liberation_sans: TrueTypeFont,
) -> None:
    # .notdef is a pure straight-line rectangle: every point is on-curve.
    g = liberation_sans.get_glyph(0)
    assert g is not None
    desc = g.get_description()
    for i in range(desc.get_point_count()):
        assert desc.get_flags(i) & GlyfDescript.ON_CURVE


def test_description_resolve_is_idempotent(liberation_sans: TrueTypeFont) -> None:
    g = liberation_sans.get_glyph(0)
    assert g is not None
    desc = g.get_description()
    desc.resolve()
    desc.resolve()
    # State after a second resolve must still match expectations.
    assert desc.get_point_count() == 8
