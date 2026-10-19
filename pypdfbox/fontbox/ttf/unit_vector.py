"""A 2D unit vector in F2Dot14 fixed point.

Used for the projection, freedom and dual-projection vectors of the TrueType
graphics state. Kept as a mutable class (not a float point type) so the
interpreter can stay in integer math. Because they are mutable,
:meth:`GraphicsState.copy` deep-copies them, so a per-glyph clone cannot write
through to the saved post-``prep`` template.

Named after FreeType's ``FT_UnitVector``, and like it the unit length is a
convention rather than an enforced invariant: ``SPVFS`` and ``SFVFS`` write
whatever the font pushed on the stack, which a malformed font need not have
normalized.
"""

from __future__ import annotations

from math import isqrt

from pypdfbox.fontbox.ttf.fixed import ONE_F2DOT14


class UnitVector:
    """Mutable F2Dot14 vector; mirrors upstream package-private ``UnitVector``."""

    __slots__ = ("_x", "_y")

    def __init__(self, x: int, y: int) -> None:
        self._x = x
        self._y = y

    @staticmethod
    def x_axis() -> UnitVector:
        """Returns the x axis unit vector (1, 0)."""
        return UnitVector(ONE_F2DOT14, 0)

    @staticmethod
    def y_axis() -> UnitVector:
        """Returns the y axis unit vector (0, 1)."""
        return UnitVector(0, ONE_F2DOT14)

    @staticmethod
    def normalize(dx: int, dy: int) -> UnitVector:
        """Builds a unit vector in F2Dot14 from a coordinate delta.

        Each component is the exact quotient ``d / |(dx, dy)|`` in 16.16 fixed
        point, rounded to nearest, then reduced to F2Dot14 by truncation
        towards zero - the reduction FreeType uses, so diagonal vectors agree
        with it. A zero-length delta falls back to the x axis.
        """
        if dx == 0 and dy == 0:
            return UnitVector.x_axis()
        if dx == 0:
            return UnitVector(0, ONE_F2DOT14 if dy > 0 else -ONE_F2DOT14)
        if dy == 0:
            return UnitVector(ONE_F2DOT14 if dx > 0 else -ONE_F2DOT14, 0)
        length_squared = dx * dx + dy * dy
        return UnitVector(
            _quarter(_component(dx, length_squared)), _quarter(_component(dy, length_squared))
        )

    def perpendicular(self) -> UnitVector:
        """Returns this vector rotated 90 degrees counter-clockwise, i.e. ``(-y, x)``."""
        return UnitVector(-self._y, self._x)

    def get_x(self) -> int:
        """Returns the x component in F2Dot14."""
        return self._x

    def get_y(self) -> int:
        """Returns the y component in F2Dot14."""
        return self._y

    def set(self, x: int, y: int) -> None:
        """Sets both components (F2Dot14)."""
        self._x = x
        self._y = y

    def copy(self) -> UnitVector:
        """Returns an independent copy of this vector."""
        return UnitVector(self._x, self._y)

    def __eq__(self, obj: object) -> bool:
        if self is obj:
            return True
        if not isinstance(obj, UnitVector):
            return False
        return self._x == obj._x and self._y == obj._y

    def __hash__(self) -> int:
        return 31 * self._x + self._y

    def __repr__(self) -> str:
        return f"UnitVector({self._x}, {self._y})"

    __str__ = __repr__


def _component(d: int, length_squared: int) -> int:
    """``round(d * 65536 / sqrt(length_squared))`` computed exactly.

    The result r is the integer whose interval ``[r - 1/2, r + 1/2)`` contains
    the quotient, i.e. the one with
    ``(2r - 1)^2 * L <= (2|d| * 65536)^2 < (2r + 1)^2 * L``, so no floating
    point is involved. Upstream starts from a floating-point estimate and
    corrects it by that inequality; with ``m = isqrt(N // L)``, the largest
    integer with ``m^2 * L <= N``, the same r is ``(m + 1) // 2`` directly.
    """
    numerator = (2 * abs(d) * 0x10000) ** 2
    r = (isqrt(numerator // length_squared) + 1) >> 1
    return -r if d < 0 else r


def _quarter(value: int) -> int:
    """Java ``value / 4``: truncation towards zero."""
    return value >> 2 if value >= 0 else -((-value) >> 2)


__all__ = ["UnitVector"]
