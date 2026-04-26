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
