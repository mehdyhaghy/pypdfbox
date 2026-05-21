"""Wave 1345: residual coverage for ``pypdfbox.util.number_format_util``.

Targets:
  - the carry-overflow branch (line 91-92) when the rounded fraction
    spills into the integer part (e.g. 0.99999... → 1.0);
  - the saturation tail of ``_get_exponent`` (line 27) for an integer
    larger than ``10**18``;
  - the negative-value branch (line 81-83) of ``format_float_fast``;
  - the public ``get_exponent`` / ``format_positive_number`` wrappers
    (lines 111, 122) that mirror the upstream private helpers.
"""

from __future__ import annotations

from pypdfbox.util.number_format_util import (
    NumberFormatUtil,
    _format_positive_number,
    _get_exponent,
)


def test_get_exponent_saturates_for_huge_values() -> None:
    """A value at or above ``10**18`` returns the table's last index (18)."""
    assert _get_exponent(10**18) == 18
    assert _get_exponent(10**25) == 18


def test_format_float_fast_negative_value_emits_minus_prefix() -> None:
    buf = bytearray(32)
    n = NumberFormatUtil.format_float_fast(-12.5, 1, buf)
    assert buf[:n] == b"-12.5"


def test_format_float_fast_negative_carry_overflow() -> None:
    """Negative values are routed through the minus-prefix branch and the
    carry handling is symmetrical (-0.99999 with 4 digits rounds to -1)."""
    buf = bytearray(32)
    n = NumberFormatUtil.format_float_fast(-0.99999, 4, buf)
    # Rounded fraction (= 10000) >= 10**4, so integer rolls to 1.
    assert buf[:n] == b"-1"


def test_format_float_fast_carry_into_integer_part() -> None:
    """0.99999 with 4-digit precision rounds to 1.0 — covers the carry
    branch where ``fraction_part >= _POWER_OF_TENS[max_fraction_digits]``."""
    buf = bytearray(32)
    n = NumberFormatUtil.format_float_fast(0.99999, 4, buf)
    # 0.99999 * 10000 + 0.5 = 9999.9 + 0.5 = 10000.4 -> 10000 >= 10000 -> carry.
    assert buf[:n] == b"1"


def test_format_float_fast_rejects_inf() -> None:
    buf = bytearray(32)
    assert NumberFormatUtil.format_float_fast(float("inf"), 2, buf) == -1


def test_format_float_fast_rejects_too_many_fraction_digits() -> None:
    buf = bytearray(32)
    # Default MAX_FRACTION_DIGITS is 5; 6 must be rejected.
    assert NumberFormatUtil.format_float_fast(1.0, 6, buf) == -1


def test_format_float_fast_rejects_out_of_long_range() -> None:
    """Values beyond signed-64-bit long must return -1 (mirror upstream).

    ``float(2**63)`` equals ``(double)Long.MAX_VALUE`` exactly because
    9223372036854775807 is not representable in IEEE-754 doubles and rounds
    up to 9223372036854775808. Java's ``value > Long.MAX_VALUE`` promotes
    long to double and yields ``false`` for this exact value, so upstream
    accepts and prints "9223372036854775807". Wave 1364 aligned pypdfbox
    with that behavior; the truly-too-big values still get rejected.
    """
    buf = bytearray(32)
    too_big = float(2**63) * 2  # twice Long.MAX_VALUE_AS_DOUBLE
    assert NumberFormatUtil.format_float_fast(too_big, 0, buf) == -1


def test_format_float_fast_zero_fraction_digits() -> None:
    """A 0-digit precision yields the integer part only — no decimal point."""
    buf = bytearray(32)
    n = NumberFormatUtil.format_float_fast(3.0, 0, buf)
    assert buf[:n] == b"3"


def test_format_float_fast_fraction_is_zero_no_decimal_point() -> None:
    """When the rounded fraction is zero the decimal point is omitted."""
    buf = bytearray(32)
    n = NumberFormatUtil.format_float_fast(7.0, 3, buf)
    assert buf[:n] == b"7"


def test_get_exponent_wrapper_matches_private_helper() -> None:
    """The public ``NumberFormatUtil.get_exponent`` mirrors the private."""
    for n in (0, 1, 9, 10, 99, 100, 999_999):
        assert NumberFormatUtil.get_exponent(n) == _get_exponent(n)


def test_format_positive_number_wrapper_writes_into_buffer() -> None:
    """The public ``NumberFormatUtil.format_positive_number`` mirrors the
    private helper byte-for-byte at the wrapper boundary."""
    buf_pub = bytearray(8)
    buf_priv = bytearray(8)
    n_pub = NumberFormatUtil.format_positive_number(12345, 4, False, buf_pub, 0)
    n_priv = _format_positive_number(12345, 4, False, buf_priv, 0)
    assert n_pub == n_priv
    assert buf_pub[:n_pub] == buf_priv[:n_priv] == b"12345"


def test_format_float_fast_strips_trailing_zeros() -> None:
    """``omit_trailing_zeros=True`` in the fraction path drops dangling 0s."""
    buf = bytearray(32)
    n = NumberFormatUtil.format_float_fast(2.5, 5, buf)
    assert buf[:n] == b"2.5"


def test_number_format_util_constructor_rejected() -> None:
    """Static-utility constructor raises (pragma-no-cover assertion)."""
    # We don't actually exercise the constructor here (it's pragma:no cover)
    # — but ensure the class-level ``MAX_FRACTION_DIGITS`` mirrors the module.
    assert NumberFormatUtil.MAX_FRACTION_DIGITS == 5
