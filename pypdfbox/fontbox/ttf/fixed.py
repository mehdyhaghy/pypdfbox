"""Integer fixed-point math for the TrueType bytecode interpreter.

The interpreter keeps coordinates in 26.6 fixed point (F26Dot6: 26 integer
bits, 6 fractional bits, so 1 pixel == 64) and the projection/freedom vectors
in 2.14 fixed point (F2Dot14). Mirroring FreeType's all-integer arithmetic,
rather than mixing in floating point, is what makes byte-exact comparison
against a FreeType reference dump possible.

Upstream ``Fixed`` is a static utility class. The helpers are plain module
functions here (so the interpreter's hot loops call them without an attribute
lookup) and :class:`Fixed` exposes the same functions as static methods.
Every result is narrowed to a Java 32-bit ``int`` exactly where upstream casts
a ``long`` back to ``int``.
"""

from __future__ import annotations

ONE = 64
"""One pixel in F26Dot6."""

HALF = 32
"""Half a pixel in F26Dot6."""

ONE_F2DOT14 = 0x4000
"""1.0 in F2Dot14."""

_INT_MIN = -0x80000000
_INT_MAX = 0x7FFFFFFF


def to_int32(value: int) -> int:
    """Narrows an unbounded Python ``int`` to a Java 32-bit ``int`` (two's complement wrap)."""
    if _INT_MIN <= value <= _INT_MAX:
        return value
    return ((value + 0x80000000) & 0xFFFFFFFF) - 0x80000000


def int_div(a: int, b: int) -> int:
    """Java integer division: the quotient truncated towards zero (``b`` must be non-zero)."""
    if (a < 0) == (b < 0):
        return a // b if a >= 0 else (-a) // (-b)
    return -(abs(a) // abs(b))


def from_int(value: int) -> int:
    """Converts an integer pixel value to F26Dot6."""
    return to_int32(value << 6)


def to_int(value: int) -> int:
    """Converts an F26Dot6 value back to an integer, rounding to nearest."""
    return to_int32(value + HALF) >> 6


def floor(value: int) -> int:
    """Rounds an F26Dot6 value down to the pixel grid (towards negative infinity)."""
    return value & ~63


def ceil(value: int) -> int:
    """Rounds an F26Dot6 value up to the pixel grid."""
    return to_int32(value + 63) & ~63


def round_(value: int) -> int:
    """Rounds an F26Dot6 value to the nearest pixel grid line (round-to-grid)."""
    return to_int32(value + HALF) & ~63


def mul_div(a: int, b: int, c: int) -> int:
    """``round(a * b / c)`` with correct sign handling, matching FreeType's ``FT_MulDiv``.

    A zero divisor yields ``0x7FFFFFFF`` with the operands' sign, as upstream does.
    """
    neg = False
    if a < 0:
        a = -a
        neg = True
    if b < 0:
        b = -b
        neg = not neg
    if c < 0:
        c = -c
        neg = not neg
    r = (a * b + (c >> 1)) // c if c else 0x7FFFFFFF
    if neg:
        r = -r
    if _INT_MIN <= r <= _INT_MAX:
        return r
    return ((r + 0x80000000) & 0xFFFFFFFF) - 0x80000000


def mul(a: int, b: int) -> int:
    """Multiplies two F26Dot6 values (the TrueType ``MUL`` operator)."""
    return mul_div(a, b, ONE)


def div(a: int, b: int) -> int:
    """Divides two F26Dot6 values (the TrueType ``DIV`` operator).

    Division by zero yields zero. Unlike :func:`mul` this *truncates* toward
    zero rather than rounding, matching FreeType's ``DIV`` opcode (which uses
    ``FT_MulDiv_No_Round``).
    """
    if b == 0:
        return 0
    neg = False
    if a < 0:
        a = -a
        neg = True
    if b < 0:
        b = -b
        neg = not neg
    r = a * ONE // b
    if neg:
        r = -r
    return to_int32(r)


def mul14(a: int, b: int) -> int:
    """Multiplies an F26Dot6 value by an F2Dot14 value, returning F26Dot6."""
    return mul_div(a, b, ONE_F2DOT14)


def mul_fix(a: int, b: int) -> int:
    """Multiplies by a 16.16 factor, rounding half away from zero: FreeType's ``FT_MulFix``."""
    c = (abs(a) * abs(b) + 0x8000) >> 16
    return to_int32(-c if (a < 0) != (b < 0) else c)


def div_fix(a: int, b: int) -> int:
    """Divides to a 16.16 quotient, rounding half away from zero: FreeType's ``FT_DivFix``.

    Division by zero yields ``0x7FFFFFFF``, as in FreeType.
    """
    la = abs(a)
    lb = abs(b)
    q = ((la << 16) + (lb >> 1)) // lb if lb > 0 else 0x7FFFFFFF
    return to_int32(-q if (a < 0) != (b < 0) else q)


def scale(funits: int, ppem: int, units_per_em: int) -> int:
    """Scales font units to F26Dot6 device pixels: ``round(funits * ppem * 64 / unitsPerEm)``.

    This is *not* a flat ``* 64``, which would only be correct when
    ``unitsPerEm == ppem``. Both control values and glyph point coordinates
    are scaled with this.
    """
    if units_per_em == 0:
        return 0
    numerator = funits * ppem * ONE
    if units_per_em > 0:
        half = units_per_em >> 1
        if numerator >= 0:
            q = (numerator + half) // units_per_em
        else:
            q = -((half - numerator) // units_per_em)
        return q if _INT_MIN <= q <= _INT_MAX else to_int32(q)
    half = int_div(units_per_em, 2)
    rounded = numerator + half if numerator >= 0 else numerator - half
    return to_int32(int_div(rounded, units_per_em))


class Fixed:
    """Static fixed-point helpers, mirroring upstream's ``Fixed`` utility class."""

    __slots__ = ()

    ONE = ONE
    HALF = HALF
    ONE_F2DOT14 = ONE_F2DOT14

    from_int = staticmethod(from_int)
    to_int = staticmethod(to_int)
    floor = staticmethod(floor)
    ceil = staticmethod(ceil)
    round = staticmethod(round_)
    mul_div = staticmethod(mul_div)
    mul = staticmethod(mul)
    div = staticmethod(div)
    mul14 = staticmethod(mul14)
    mul_fix = staticmethod(mul_fix)
    div_fix = staticmethod(div_fix)
    scale = staticmethod(scale)

    def __init__(self) -> None:
        raise TypeError("Fixed is a static utility class")


__all__ = [
    "HALF",
    "ONE",
    "ONE_F2DOT14",
    "Fixed",
    "ceil",
    "div",
    "div_fix",
    "floor",
    "from_int",
    "int_div",
    "mul",
    "mul14",
    "mul_div",
    "mul_fix",
    "round_",
    "scale",
    "to_int",
    "to_int32",
]
