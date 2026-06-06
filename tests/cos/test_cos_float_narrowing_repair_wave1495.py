"""Wave 1495 — behaviour-anchored coverage for ``COSFloat``'s JVM-narrowing
saturation casts and the ``COSFloat(String)`` malformed-real repair block.

These exercise the branches the existing ``test_cos_float*`` suite leaves
untouched: the ``f2i`` / ``f2l`` saturating clamps (and ``NaN`` → 0), the three
regex-guided ``catch``-block repairs (PDFBOX-2990 / -3500), the
unrecoverable-literal raise, and the ``_float32_or_inf`` overflow-to-infinity
path that drives the constructor's verbatim-string-discard decision.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSFloat
from pypdfbox.cos.cos_float import (
    _INT_MAX,
    _INT_MIN,
    _LONG_MAX,
    _LONG_MIN,
    _float32_or_inf,
    _narrow_to_long,
)

# ---------- f2i / f2l saturating narrowing casts ----------


def test_int_value_saturates_at_int_max_for_huge_magnitude() -> None:
    # 1e40 overflows float32 -> Float.MAX_VALUE (~3.4e38), well past 2**31-1,
    # so ``f2i`` saturates to Integer.MAX_VALUE rather than overflowing.
    f = COSFloat("1e40")
    assert f.int_value() == _INT_MAX


def test_int_value_saturates_at_int_min_for_huge_negative_magnitude() -> None:
    f = COSFloat("-1e40")
    assert f.int_value() == _INT_MIN


def test_long_value_saturates_at_long_max_for_huge_magnitude() -> None:
    f = COSFloat("1e40")
    assert f.long_value() == _LONG_MAX


def test_long_value_saturates_at_long_min_for_huge_negative_magnitude() -> None:
    f = COSFloat("-1e40")
    assert f.long_value() == _LONG_MIN


def test_narrow_to_long_maps_nan_to_zero() -> None:
    assert _narrow_to_long(math.nan, _INT_MIN, _INT_MAX) == 0


def test_narrow_to_long_truncates_toward_zero() -> None:
    # Round toward zero, not floor: -2.9 -> -2, 2.9 -> 2.
    assert _narrow_to_long(-2.9, _INT_MIN, _INT_MAX) == -2
    assert _narrow_to_long(2.9, _INT_MIN, _INT_MAX) == 2


def test_int_value_of_nan_cosfloat_is_zero() -> None:
    f = COSFloat(float("nan"))
    assert f.int_value() == 0
    assert f.long_value() == 0


# ---------- malformed-real repair (COSFloat(String) catch block) ----------


def test_repair_double_leading_minus_drops_first_char() -> None:
    # ``--16.33`` -> drop first char -> ``-16.33``; repair path leaves the
    # cached original null, so it reformats from the float.
    f = COSFloat("--16.33")
    assert f.float_value() == pytest.approx(-16.33, rel=1e-6)
    assert f.get_original_form() is None


def test_repair_leading_zero_dash_fraction() -> None:
    # ``0.-262`` -> ``-0.262`` (prepend ``-`` and delete first interior ``-``).
    f = COSFloat("0.-262")
    assert f.float_value() == pytest.approx(-0.262, rel=1e-6)
    assert f.get_original_form() is None


def test_repair_dash_fraction_dash() -> None:
    # ``-16.-33`` -> ``-16.33`` (prepend ``-`` and strip every ``-``).
    f = COSFloat("-16.-33")
    assert f.float_value() == pytest.approx(-16.33, rel=1e-6)
    assert f.get_original_form() is None


def test_unrecoverable_literal_raises_oserror() -> None:
    # Not matched by any of the three repair regexes -> OSError (Java
    # IOException) with the expected message text.
    with pytest.raises(OSError, match="floating point number"):
        COSFloat("not-a-number")


def test_repair_then_failed_parse_raises_oserror() -> None:
    # A leading ``--`` triggers the first repair (drops one ``-``) but the
    # remainder still doesn't parse as a Java float -> OSError.
    with pytest.raises(OSError, match="floating point number"):
        COSFloat("--xx")


# ---------- _float32_or_inf overflow-to-infinity ----------


def test_float32_or_inf_overflows_huge_positive_double_to_inf() -> None:
    assert _float32_or_inf(1e40) == math.inf


def test_float32_or_inf_overflows_huge_negative_double_to_neg_inf() -> None:
    assert _float32_or_inf(-1e40) == -math.inf


def test_float32_or_inf_passes_nan_through() -> None:
    assert math.isnan(_float32_or_inf(math.nan))


def test_overflowing_literal_discards_verbatim_string() -> None:
    # ``1e40`` parses to +inf in float32, coerce maps it to MAX_VALUE; because
    # parsed (+inf) != coerced (MAX_VALUE) the verbatim string is discarded.
    f = COSFloat("1e40")
    assert f.get_original_form() is None
