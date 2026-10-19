"""Hand-written tests for ``fixed``: Java 32-bit ``int`` narrowing and rounding edge cases."""

import pytest

from pypdfbox.fontbox.ttf import fixed
from pypdfbox.fontbox.ttf.fixed import Fixed

INT_MIN = -(2**31)
INT_MAX = 2**31 - 1


def _java_mul_div(a, b, c):
    """Straight transcription of upstream mulDiv with explicit long/int semantics."""
    sign = 1
    la, lb, lc = a, b, c
    if la < 0:
        la, sign = -la, -sign
    if lb < 0:
        lb, sign = -lb, -sign
    if lc < 0:
        lc, sign = -lc, -sign
    result = (la * lb + lc // 2) // lc if lc != 0 else 0x7FFFFFFF
    return fixed.to_int32(sign * result)


def test_to_int32_wraps_like_a_java_int():
    assert fixed.to_int32(INT_MAX + 1) == INT_MIN
    assert fixed.to_int32(INT_MIN - 1) == INT_MAX
    assert fixed.to_int32(2**32 + 5) == 5
    assert fixed.to_int32(-5) == -5


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(7, 2, 3), (-7, 2, -3), (7, -2, -3), (-7, -2, 3), (0, 5, 0), (1, 2, 0), (-1, 2, 0)],
)
def test_int_div_truncates_toward_zero(a, b, expected):
    assert fixed.int_div(a, b) == expected


def test_from_int_and_ceil_wrap():
    assert Fixed.from_int(2**25) == INT_MIN  # 2^31 wraps
    assert Fixed.ceil(INT_MAX) == INT_MIN  # (MAX + 63) wraps before the mask
    assert Fixed.round(INT_MAX) == INT_MIN
    assert Fixed.to_int(INT_MAX) == INT_MIN >> 6


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (100, 64, 64),
        (-100, 3, 7),
        (INT_MAX, INT_MAX, 1),  # the long product wraps when narrowed
        (INT_MIN, INT_MIN, 3),
        (INT_MIN, 1, -1),
        (5, 5, 0),  # zero divisor: 0x7FFFFFFF with the operands' sign
        (-5, 5, 0),
        (12345, -16384, 11585),
    ],
)
def test_mul_div_matches_the_java_transcription(a, b, c):
    assert Fixed.mul_div(a, b, c) == _java_mul_div(a, b, c)


def test_mul_div_identity_fast_path_assumption():
    # ExecutionContext.move_point relies on mul_div(d, f, f) == d for every f != 0
    for d in (-1000, -1, 0, 1, 31, 32, 33, 1000, INT_MAX, INT_MIN):
        for f in (1, -1, 0x400, -0x2D41, 0x4000, -0x4000, 12345):
            assert Fixed.mul_div(d, f, f) == d


def test_div_truncates_and_wraps():
    assert Fixed.div(-65, 64) == -65  # (-65 * 64) / 64, no rounding
    assert Fixed.div(1, 3) == 21  # 64 / 3 = 21.33 truncated
    assert Fixed.div(-1, 3) == -21
    assert Fixed.div(INT_MAX, 1) == fixed.to_int32(INT_MAX * 64)
    assert Fixed.div(INT_MIN, 0) == 0


def test_mul_fix_rounds_half_away_from_zero():
    assert Fixed.mul_fix(1, 0x8000) == 1  # 0.5 rounds away from zero
    assert Fixed.mul_fix(-1, 0x8000) == -1
    assert Fixed.mul_fix(3, -0x10000) == -3
    assert Fixed.mul_fix(0, -5) == 0


def test_div_fix():
    assert Fixed.div_fix(1, 2) == 0x8000
    assert Fixed.div_fix(-1, 3) == -21845
    assert Fixed.div_fix(5, 0) == 0x7FFFFFFF
    assert Fixed.div_fix(-5, 0) == -0x7FFFFFFF


def test_scale_rounding_and_signs():
    assert Fixed.scale(-1000, 16, 2048) == -500
    assert Fixed.scale(1, 16, 2048) == 1  # 0.5 rounds away from zero
    assert Fixed.scale(-1, 16, 2048) == -1
    # a negative unitsPerEm follows upstream literally: the half is added with the numerator's
    # sign (so it pulls toward zero here) and the long division truncates
    assert Fixed.scale(1000, 16, -2048) == -499
    assert Fixed.scale(-1000, 16, -2049) == 499


def test_fixed_is_not_instantiable():
    with pytest.raises(TypeError):
        Fixed()
