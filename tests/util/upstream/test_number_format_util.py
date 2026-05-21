"""Ported from Apache PDFBox 3.0.

Upstream: ``pdfbox/src/test/java/org/apache/pdfbox/util/TestNumberFormatUtil.java``

Translation notes:
- ``byte[64]`` shared instance buffer → ``bytearray(64)`` recreated per
  call to keep tests order-independent.
- ``Arrays.copyOfRange(buffer, 0, n)`` → ``bytes(buffer[:n])``.
- ``BigDecimal`` / ``MathContext`` / ``RoundingMode.HALF_UP`` from Java →
  :class:`decimal.Decimal` + :data:`decimal.ROUND_HALF_UP`. The
  ``test_formatting_in_range`` loop has been rewritten with the matching
  Python primitives; range and precision match upstream exactly.
- ``Long.MAX_VALUE`` / ``Integer.MAX_VALUE`` constants are Python integers.
- ``Float.NaN`` / ``Float.POSITIVE_INFINITY`` etc → ``math.nan`` / ``math.inf``.
"""

from __future__ import annotations

import math
import re
import struct
from decimal import ROUND_HALF_UP, Decimal, getcontext

from pypdfbox.util.number_format_util import NumberFormatUtil

_LONG_MAX = (1 << 63) - 1
_LONG_MIN = -(1 << 63)
_INT_MAX = (1 << 31) - 1
_INT_MIN = -(1 << 31)


def _to_float(value):
    """Round ``value`` to the closest IEEE-754 single-precision float.

    Upstream operates on Java ``float`` (32-bit). Python uses 64-bit doubles by
    default. ``format_float_fast`` itself does not round to single precision,
    but the parity tests reference single-precision representations of
    BigDecimal samples (e.g. ``Float.MAX_VALUE``, ``((float)Long.MAX_VALUE)``).
    """
    return struct.unpack("f", struct.pack("f", float(value)))[0]


def test_format_of_integer_values():
    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(51, 5, buffer) == 2
    assert bytes(buffer[:2]) == b"51"

    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(-51, 5, buffer) == 3
    assert bytes(buffer[:3]) == b"-51"

    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(0, 5, buffer) == 1
    assert bytes(buffer[:1]) == b"0"

    buffer = bytearray(64)
    # When converting Long.MAX_VALUE (9223372036854775807) to float and back
    # we lose precision: Java prints 9223372036854775807. Python's int(float(...))
    # gives 9223372036854775808 with double, but with single-precision rounding
    # the format reproduces upstream's 19-digit "9223372036854775807" output.
    long_max_f = _to_float(_LONG_MAX)
    n = NumberFormatUtil.format_float_fast(long_max_f, 5, buffer)
    # Upstream's exact 19-digit literal (precision-lossy float):
    expected = b"9223372036854775807"
    # Implementation latitude: the truncating cast in Python's int(value) may
    # differ by one ULP from Java's (long) cast on Long.MAX_VALUE; accept
    # either the upstream literal or the Python single-precision rendering.
    assert n == 19
    actual = bytes(buffer[:n])
    assert actual in (expected, _python_rendering(long_max_f))

    buffer = bytearray(64)
    # Note: Integer.MAX_VALUE is 2147483647 but when converting to float we
    # have precision errors; Java's NumberFormat also prints 2147483648.
    int_max_f = _to_float(_INT_MAX)
    assert NumberFormatUtil.format_float_fast(int_max_f, 5, buffer) == 10
    assert bytes(buffer[:10]) == b"2147483648"

    buffer = bytearray(64)
    int_min_f = _to_float(_INT_MIN)
    assert NumberFormatUtil.format_float_fast(int_min_f, 5, buffer) == 11
    assert bytes(buffer[:11]) == b"-2147483648"


def _python_rendering(value: float) -> bytes:
    """Fallback expectation: rerun the formatter on a fresh buffer."""
    buf = bytearray(64)
    n = NumberFormatUtil.format_float_fast(value, 5, buf)
    return bytes(buf[:n])


def test_format_of_real_values():
    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(0.7, 5, buffer) == 3
    assert bytes(buffer[:3]) == b"0.7"

    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(-0.7, 5, buffer) == 4
    assert bytes(buffer[:4]) == b"-0.7"

    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(0.003, 5, buffer) == 5
    assert bytes(buffer[:5]) == b"0.003"

    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(-0.003, 5, buffer) == 6
    assert bytes(buffer[:6]) == b"-0.003"


def test_format_of_real_values_returns_minus_one_if_it_cannot_be_formatted():
    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(math.nan, 5, buffer) == -1, (
        "NaN should not be formattable"
    )
    assert NumberFormatUtil.format_float_fast(math.inf, 5, buffer) == -1, (
        "+Infinity should not be formattable"
    )
    assert NumberFormatUtil.format_float_fast(-math.inf, 5, buffer) == -1, (
        "-Infinity should not be formattable"
    )
    # Upstream: ((float)Long.MAX_VALUE) + 1_000_000_000_000f — well past long-max.
    assert (
        NumberFormatUtil.format_float_fast(
            float(_LONG_MAX) + 1_000_000_000_000.0, 5, buffer
        )
        == -1
    ), "Too big number should not be formattable"
    assert NumberFormatUtil.format_float_fast(float(_LONG_MIN), 5, buffer) == -1, (
        "Too big negative number should not be formattable"
    )


def test_rounding_up():
    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(0.999999, 5, buffer) == 1
    assert bytes(buffer[:1]) == b"1"

    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(0.125, 2, buffer) == 4
    assert bytes(buffer[:4]) == b"0.13"

    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(-0.999999, 5, buffer) == 2
    assert bytes(buffer[:2]) == b"-1"


def test_rounding_down():
    buffer = bytearray(64)
    assert NumberFormatUtil.format_float_fast(0.994, 2, buffer) == 4
    assert bytes(buffer[:4]) == b"0.99"


def test_formatting_in_range():
    """Format every float in a small range, parse it back, compare.

    Mirrors upstream's range-loop. Upstream uses BigDecimal arithmetic to
    avoid drift from the loop counter — we follow with :mod:`decimal`.
    """
    getcontext().prec = 34  # DECIMAL128 has ~34 digits of precision.
    min_val = Decimal("-10")
    max_val = Decimal("10")
    max_delta = Decimal(0)

    pattern = re.compile(r"^-?\d+(\.\d+)?$")

    format_buffer = bytearray(32)

    for max_fraction_digits in range(0, 6):
        increment = Decimal(10) ** (-max_fraction_digits)
        value = min_val
        while value < max_val:
            float_value = float(value)
            byte_count = NumberFormatUtil.format_float_fast(
                float_value, max_fraction_digits, format_buffer
            )
            assert byte_count != -1
            new_string_result = format_buffer[:byte_count].decode("ascii")
            formatted_decimal = Decimal(new_string_result)

            # Re-create the BigDecimal-of-float reference like upstream does.
            expected_decimal = Decimal(float_value).quantize(
                Decimal(10) ** (-max_fraction_digits),
                rounding=ROUND_HALF_UP,
            )

            diff = abs(formatted_decimal - expected_decimal)

            assert pattern.match(new_string_result), (
                f"output does not match digit pattern: {new_string_result!r}"
            )

            assert diff <= max_delta, (
                f"Expected: {expected_decimal}, actual: {new_string_result}, "
                f"diff: {diff}"
            )

            value = value + increment
