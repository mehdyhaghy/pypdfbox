"""2D vector value object.

Mirrors ``org.apache.pdfbox.util.Vector`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/Vector.java``).
"""

from __future__ import annotations


class Vector:
    """Immutable 2D vector with float components."""

    __slots__ = ("_x", "_y")

    def __init__(self, x: float, y: float) -> None:
        self._x = float(x)
        self._y = float(y)

    def get_x(self) -> float:
        """Return the x magnitude."""
        return self._x

    def get_y(self) -> float:
        """Return the y magnitude."""
        return self._y

    def scale(self, sxy: float) -> Vector:
        """Return a new vector with both components scaled by ``sxy``."""
        return Vector(self._x * sxy, self._y * sxy)

    def to_string(self) -> str:
        """Mirror upstream ``Vector.toString``."""
        return f"({self._x}, {self._y})"

    def __repr__(self) -> str:
        return self.to_string()


__all__ = ["Vector"]
