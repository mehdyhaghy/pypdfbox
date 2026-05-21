"""Fast float formatter used by ``COSWriter``.

Mirrors ``org.apache.pdfbox.util.NumberFormatUtil`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/NumberFormatUtil.java``).

Upstream avoids ``DecimalFormat`` and the JDK NumberFormat lock by writing
ASCII digits directly into a caller-provided ``byte[]``. We mirror that
shape for parity so callers can swap implementations transparently.
"""

from __future__ import annotations

import math

MAX_FRACTION_DIGITS = 5

_POWER_OF_TENS = [10**i for i in range(19)]
_LONG_MAX = (1 << 63) - 1
_LONG_MIN = -(1 << 63)
_INT_MAX = (1 << 31) - 1
# Upstream's bounds check ``value > Long.MAX_VALUE`` promotes ``Long.MAX_VALUE``
# to a double before comparing — exactly ``2**63`` because ``9223372036854775807``
# is not representable in IEEE-754 doubles and rounds up. Python's ``int``/
# ``float`` comparison uses exact integer semantics, so ``2**63 > 2**63 - 1``
# would (incorrectly) reject any double-promoted ``Long.MAX_VALUE``. Mirror
# Java by comparing in double space.
_LONG_MAX_AS_DOUBLE = float(_LONG_MAX)
_LONG_MIN_AS_DOUBLE = float(_LONG_MIN)


def _get_exponent(number: int) -> int:
    for exp in range(len(_POWER_OF_TENS) - 1):
        if number < _POWER_OF_TENS[exp + 1]:
            return exp
    return len(_POWER_OF_TENS) - 1


def _format_positive_number(
    number: int,
    exp: int,
    omit_trailing_zeros: bool,
    ascii_buffer: bytearray,
    start_offset: int,
) -> int:
    offset = start_offset
    remaining = number
    while exp >= 0 and (not omit_trailing_zeros or remaining > 0):
        digit = remaining // _POWER_OF_TENS[exp]
        remaining -= digit * _POWER_OF_TENS[exp]
        ascii_buffer[offset] = ord("0") + digit
        offset += 1
        exp -= 1
    return offset


class NumberFormatUtil:
    """Static-only formatter mirroring upstream's ``formatFloatFast``."""

    MAX_FRACTION_DIGITS = MAX_FRACTION_DIGITS

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("NumberFormatUtil is a utility class")

    @staticmethod
    def format_float_fast(
        value: float,
        max_fraction_digits: int,
        ascii_buffer: bytearray,
    ) -> int:
        """Write ``value`` as ASCII into ``ascii_buffer``.

        Returns the number of bytes written, or ``-1`` if ``value`` is NaN,
        infinite, out of ``long`` range or ``max_fraction_digits`` exceeds
        :data:`MAX_FRACTION_DIGITS`.
        """
        if (
            math.isnan(value)
            or math.isinf(value)
            or value > _LONG_MAX_AS_DOUBLE
            or value <= _LONG_MIN_AS_DOUBLE
            or max_fraction_digits > MAX_FRACTION_DIGITS
        ):
            return -1

        offset = 0
        # Java casts the double to long — saturating at Long.MAX_VALUE / MIN.
        # Python's ``int(float)`` truncates toward zero; for non-saturating
        # values it matches Java exactly, but for ``(double)Long.MAX_VALUE`` —
        # which equals ``2**63`` — Java clamps to ``Long.MAX_VALUE`` while
        # Python yields ``2**63``. Clamp explicitly for parity.
        if value >= _LONG_MAX_AS_DOUBLE:
            integer_part = _LONG_MAX
        elif value <= _LONG_MIN_AS_DOUBLE:
            integer_part = _LONG_MIN
        else:
            integer_part = int(value)  # truncates toward zero, matches Java cast

        if value < 0:
            ascii_buffer[offset] = ord("-")
            offset += 1
            integer_part = -integer_part

        # Half-away-from-zero rounding mirrors upstream's `+ 0.5d`.
        fraction_part = int(
            (abs(value) - abs(integer_part)) * _POWER_OF_TENS[max_fraction_digits] + 0.5
        )

        if fraction_part >= _POWER_OF_TENS[max_fraction_digits]:
            integer_part += 1
            fraction_part -= _POWER_OF_TENS[max_fraction_digits]

        offset = _format_positive_number(
            integer_part, _get_exponent(integer_part), False, ascii_buffer, offset
        )

        if fraction_part > 0 and max_fraction_digits > 0:
            ascii_buffer[offset] = ord(".")
            offset += 1
            offset = _format_positive_number(
                fraction_part, max_fraction_digits - 1, True, ascii_buffer, offset
            )

        return offset

    # --- Upstream parity surface --------------------------------------
    @staticmethod
    def get_exponent(number: int) -> int:
        """Mirror of ``NumberFormatUtil.getExponent`` (upstream private)."""
        return _get_exponent(number)

    @staticmethod
    def format_positive_number(
        number: int,
        exp: int,
        omit_trailing_zeros: bool,
        ascii_buffer: bytearray,
        start_offset: int,
    ) -> int:
        """Mirror of ``NumberFormatUtil.formatPositiveNumber`` (upstream private)."""
        return _format_positive_number(
            number, exp, omit_trailing_zeros, ascii_buffer, start_offset
        )


__all__ = ["NumberFormatUtil", "MAX_FRACTION_DIGITS"]
