from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDRectangle


def test_default_constructor_zero() -> None:
    r = PDRectangle()
    assert r.lower_left_x == 0.0
    assert r.lower_left_y == 0.0
    assert r.upper_right_x == 0.0
    assert r.upper_right_y == 0.0


def test_constructor_from_four_floats() -> None:
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert r.lower_left_x == 10.0
    assert r.lower_left_y == 20.0
    assert r.upper_right_x == 110.0
    assert r.upper_right_y == 220.0


def test_width_and_height_properties() -> None:
    r = PDRectangle(0.0, 0.0, 612.0, 792.0)
    assert r.width == 612.0
    assert r.height == 792.0
    assert r.get_width() == 612.0
    assert r.get_height() == 792.0


def test_from_xywh() -> None:
    r = PDRectangle.from_xywh(10.0, 20.0, 100.0, 200.0)
    assert r.upper_right_x == 110.0
    assert r.upper_right_y == 220.0
    assert r.width == 100.0


def test_from_cos_array_round_trip() -> None:
    arr = COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0), COSFloat(4.0)])
    r = PDRectangle.from_cos_array(arr)
    assert r.lower_left_x == 1.0
    assert r.upper_right_y == 4.0
    out = r.to_cos_array()
    assert out.size() == 4
    assert out.is_direct() is True


def test_from_cos_array_normalises_swapped_corners() -> None:
    # PDF spec §7.9.5: lower-left/upper-right ordering is unimportant;
    # we normalise so width/height are non-negative.
    arr = COSArray([COSFloat(100.0), COSFloat(200.0), COSFloat(0.0), COSFloat(0.0)])
    r = PDRectangle.from_cos_array(arr)
    assert r.lower_left_x == 0.0
    assert r.upper_right_x == 100.0
    assert r.width == 100.0


def test_from_cos_array_accepts_integers() -> None:
    arr = COSArray(
        [COSInteger.get(0), COSInteger.get(0), COSInteger.get(612), COSInteger.get(792)]
    )
    r = PDRectangle.from_cos_array(arr)
    assert r.width == 612.0
    assert r.height == 792.0


def test_from_cos_array_rejects_short_array() -> None:
    arr = COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(10.0)])
    with pytest.raises(ValueError):
        PDRectangle.from_cos_array(arr)


def test_from_cos_array_rejects_non_numeric() -> None:
    arr = COSArray(
        [COSFloat(0.0), COSFloat(0.0), COSString("nope"), COSFloat(0.0)]
    )
    with pytest.raises(TypeError):
        PDRectangle.from_cos_array(arr)


def test_letter_constant() -> None:
    letter: PDRectangle = PDRectangle.LETTER  # type: ignore[attr-defined]
    assert letter.width == 612.0
    assert letter.height == 792.0


def test_setters_round_trip() -> None:
    r = PDRectangle()
    r.set_lower_left_x(1.0)
    r.set_lower_left_y(2.0)
    r.set_upper_right_x(3.0)
    r.set_upper_right_y(4.0)
    assert (r.lower_left_x, r.lower_left_y, r.upper_right_x, r.upper_right_y) == (
        1.0,
        2.0,
        3.0,
        4.0,
    )


def test_to_cos_array_emits_floats() -> None:
    r = PDRectangle(0.0, 0.0, 100.0, 200.0)
    arr = r.to_cos_array()
    for i in range(4):
        assert isinstance(arr.get(i), COSFloat)


def test_equality_and_hash() -> None:
    a = PDRectangle(0.0, 0.0, 10.0, 20.0)
    b = PDRectangle(0.0, 0.0, 10.0, 20.0)
    c = PDRectangle(0.0, 0.0, 10.0, 21.0)
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    # Non-rectangle comparison.
    assert (a == COSName.get_pdf_name("foo")) is False


# ---------- contains ----------


def test_contains_inside_point() -> None:
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert r.contains(50.0, 100.0) is True


def test_contains_outside_point() -> None:
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert r.contains(0.0, 0.0) is False
    assert r.contains(200.0, 100.0) is False
    assert r.contains(50.0, 500.0) is False


def test_contains_edge_inclusive() -> None:
    # Upstream ``contains`` is inclusive on all four edges.
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert r.contains(10.0, 20.0) is True  # lower-left corner
    assert r.contains(110.0, 220.0) is True  # upper-right corner
    assert r.contains(10.0, 100.0) is True  # left edge
    assert r.contains(50.0, 220.0) is True  # top edge


# ---------- create_retranslated_rectangle ----------


def test_create_retranslated_rectangle() -> None:
    r = PDRectangle(100.0, 100.0, 400.0, 400.0)
    t = r.create_retranslated_rectangle()
    assert t.lower_left_x == 0.0
    assert t.lower_left_y == 0.0
    assert t.upper_right_x == 300.0
    assert t.upper_right_y == 300.0


def test_create_retranslated_rectangle_returns_new_instance() -> None:
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    t = r.create_retranslated_rectangle()
    assert t is not r
    # Original unchanged.
    assert r.lower_left_x == 10.0
    assert r.lower_left_y == 20.0
    # Translated dimensions match.
    assert t.width == r.width
    assert t.height == r.height


# ---------- paper-size constants ----------


def test_points_per_inch_constant() -> None:
    assert PDRectangle.POINTS_PER_INCH == 72.0


def test_points_per_mm_constant() -> None:
    assert pytest.approx(72.0 / 25.4) == PDRectangle.POINTS_PER_MM


def test_tabloid_constant() -> None:
    tabloid: PDRectangle = PDRectangle.TABLOID  # type: ignore[attr-defined]
    assert tabloid.width == pytest.approx(11.0 * 72.0)
    assert tabloid.height == pytest.approx(17.0 * 72.0)


def test_a_series_constants() -> None:
    # A-series sizes are computed as ``mm * POINTS_PER_MM``. Values match
    # ISO 216 paper sizes within float tolerance.
    ppmm = 72.0 / 25.4
    a_sizes = {
        "A0": (PDRectangle.A0, 841.0, 1189.0),  # type: ignore[attr-defined]
        "A1": (PDRectangle.A1, 594.0, 841.0),  # type: ignore[attr-defined]
        "A2": (PDRectangle.A2, 420.0, 594.0),  # type: ignore[attr-defined]
        "A3": (PDRectangle.A3, 297.0, 420.0),  # type: ignore[attr-defined]
        "A5": (PDRectangle.A5, 148.0, 210.0),  # type: ignore[attr-defined]
        "A6": (PDRectangle.A6, 105.0, 148.0),  # type: ignore[attr-defined]
    }
    for _name, (rect, mm_w, mm_h) in a_sizes.items():
        assert rect.width == pytest.approx(mm_w * ppmm)
        assert rect.height == pytest.approx(mm_h * ppmm)


# ---------- to_general_path ----------


def test_to_general_path_returns_four_corners() -> None:
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    corners = r.to_general_path()
    # Counter-clockwise from lower-left, mirrors upstream ``toGeneralPath`` order.
    assert corners == [(10.0, 20.0), (110.0, 20.0), (110.0, 220.0), (10.0, 220.0)]


def test_to_general_path_is_closed_polygon() -> None:
    # Path should contain exactly 4 distinct corners (closing edge implicit).
    r = PDRectangle(0.0, 0.0, 100.0, 50.0)
    corners = r.to_general_path()
    assert len(corners) == 4
    # First and last edge connect implicitly.
    assert corners[0] != corners[-1]


def test_to_general_path_zero_size_rectangle() -> None:
    # Degenerate rectangle (point) should still emit four corners, all equal.
    r = PDRectangle(50.0, 50.0, 50.0, 50.0)
    corners = r.to_general_path()
    assert corners == [(50.0, 50.0), (50.0, 50.0), (50.0, 50.0), (50.0, 50.0)]


def test_to_general_path_negative_coordinates() -> None:
    # Origin in negative space — corner ordering still preserved.
    r = PDRectangle(-50.0, -100.0, 50.0, 100.0)
    corners = r.to_general_path()
    assert corners == [
        (-50.0, -100.0),
        (50.0, -100.0),
        (50.0, 100.0),
        (-50.0, 100.0),
    ]


# ---------- huge-value clamping (PDFBOX-2818) ----------


def test_from_cos_array_clamps_huge_positive_values() -> None:
    # Upstream PDFBOX-2818: values > Integer.MAX_VALUE are clipped.
    huge = 1e20  # well past 2**31 - 1
    arr = COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(huge), COSFloat(huge)])
    r = PDRectangle.from_cos_array(arr)
    int32_max = float(2**31 - 1)
    assert r.upper_right_x == int32_max
    assert r.upper_right_y == int32_max


def test_from_cos_array_clamps_huge_negative_values() -> None:
    huge_neg = -1e20
    arr = COSArray(
        [COSFloat(huge_neg), COSFloat(huge_neg), COSFloat(0.0), COSFloat(0.0)]
    )
    r = PDRectangle.from_cos_array(arr)
    int32_max = float(2**31 - 1)
    assert r.lower_left_x == -int32_max
    assert r.lower_left_y == -int32_max


def test_from_cos_array_does_not_clamp_normal_values() -> None:
    # Sanity guard — normal-range values pass through unchanged.
    arr = COSArray(
        [COSFloat(10.0), COSFloat(20.0), COSFloat(610.0), COSFloat(790.0)]
    )
    r = PDRectangle.from_cos_array(arr)
    assert r.lower_left_x == 10.0
    assert r.upper_right_y == 790.0


def test_from_cos_array_clamps_at_int32_boundary() -> None:
    # Value exactly at ``2**31 - 1`` is *not* clamped (boundary is exclusive).
    int32_max = float(2**31 - 1)
    arr = COSArray(
        [
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(int32_max),
            COSFloat(int32_max),
        ]
    )
    r = PDRectangle.from_cos_array(arr)
    assert r.upper_right_x == int32_max
    assert r.upper_right_y == int32_max
