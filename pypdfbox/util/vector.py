"""2D vector value object.

Mirrors ``org.apache.pdfbox.util.Vector`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/Vector.java``).
"""

from __future__ import annotations

from pypdfbox.util.matrix import f32


class Vector:
    """Immutable 2D vector with float components.

    Upstream ``org.apache.pdfbox.util.Vector`` stores ``float`` fields (32-bit),
    so the components are narrowed to single precision on construction and the
    ``scale`` product is computed in float arithmetic — matching Apache PDFBox's
    observable values (e.g. ``new Vector(0.1f, 0.2f).scale(0.3f)`` →
    ``0.030000001``, not ``0.03``).
    """

    __slots__ = ("_x", "_y")

    def __init__(self, x: float, y: float) -> None:
        self._x = f32(x)
        self._y = f32(y)

    def get_x(self) -> float:
        """Return the x magnitude."""
        return self._x

    def get_y(self) -> float:
        """Return the y magnitude."""
        return self._y

    def scale(self, sxy: float) -> Vector:
        """Return a new vector with both components scaled by ``sxy``."""
        sxy = f32(sxy)
        return Vector(f32(self._x * sxy), f32(self._y * sxy))

    def to_string(self) -> str:
        """Mirror upstream ``Vector.toString``."""
        from pypdfbox.cos.cos_float import format_float32

        return f"({format_float32(self._x)}, {format_float32(self._y)})"

    def __repr__(self) -> str:
        return self.to_string()


__all__ = ["Vector"]
