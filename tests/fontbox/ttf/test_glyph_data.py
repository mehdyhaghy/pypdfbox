"""Tests for :class:`pypdfbox.fontbox.ttf.GlyphData`.

Loads LiberationSans-Regular and exercises the bbox / contour-count /
path accessors against well-known glyphs (``.notdef`` at gid 0 plus a
couple of real outlines).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import BoundingBox, GlyphData, TrueTypeFont

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
