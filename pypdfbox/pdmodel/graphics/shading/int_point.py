"""Integer-coordinate point used by Gouraud shading rasterisation.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.IntPoint``.

Upstream marks this class as deprecated (the map that used it was replaced
with a 2D array) but it is still part of the package's published source so
we mirror the type for parity. It behaves like a plain ``(x, y)`` value
object with a faster hash.
"""

from __future__ import annotations


class IntPoint:
    """A 2D point with integer coordinates and a fast :py:meth:`__hash__`."""

    __slots__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        self.x = int(x)
        self.y = int(y)

    def __hash__(self) -> int:
        # Matches upstream: 89 * (623 + x) + y
        return 89 * (623 + self.x) + self.y

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, IntPoint):
            return False
        return self.x == other.x and self.y == other.y

    def __repr__(self) -> str:
        return f"IntPoint({self.x}, {self.y})"
