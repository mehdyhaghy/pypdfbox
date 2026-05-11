"""3x3 affine matrix used throughout PDF graphics.

Mirrors ``org.apache.pdfbox.util.Matrix`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/Matrix.java``).

The internal layout matches upstream — a flat list of 9 floats holding::

    sx hy 0
    hx sy 0
    tx ty 1

Note that ``hx`` and ``hy`` are reversed vs. the PDF spec to align with
Java's ``AffineTransform`` shear definitions.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.cos.cos_array import COSArray
    from pypdfbox.cos.cos_base import COSBase
    from pypdfbox.util.vector import Vector

SIZE = 9


def _is_finite(values: list[float]) -> bool:
    return all(math.isfinite(v) for v in values)


def _check_float_values(values: list[float]) -> list[float]:
    if not _is_finite(values):
        raise ValueError("Multiplying two matrices produces illegal values")
    return values


def _multiply_arrays(a: list[float], b: list[float]) -> list[float]:
    c = [0.0] * SIZE
    c[0] = a[0] * b[0] + a[1] * b[3] + a[2] * b[6]
    c[1] = a[0] * b[1] + a[1] * b[4] + a[2] * b[7]
    c[2] = a[0] * b[2] + a[1] * b[5] + a[2] * b[8]
    c[3] = a[3] * b[0] + a[4] * b[3] + a[5] * b[6]
    c[4] = a[3] * b[1] + a[4] * b[4] + a[5] * b[7]
    c[5] = a[3] * b[2] + a[4] * b[5] + a[5] * b[8]
    c[6] = a[6] * b[0] + a[7] * b[3] + a[8] * b[6]
    c[7] = a[6] * b[1] + a[7] * b[4] + a[8] * b[7]
    c[8] = a[6] * b[2] + a[7] * b[5] + a[8] * b[8]
    return c


class Matrix:
    """3x3 affine transform with the upstream's ergonomics."""

    SIZE = SIZE

    def __init__(self, *args: float) -> None:
        if not args:
            # Identity matrix (no-arg ctor in Java).
            self._single: list[float] = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
            return
        if len(args) == 1:
            (raw,) = args
            if isinstance(raw, list) and len(raw) == SIZE:
                # Private ctor: do not clone.
                self._single = raw
                return
            raise TypeError("Matrix constructor accepts () or 6 floats")
        if len(args) == 6:
            a, b, c, d, e, f = (float(v) for v in args)
            self._single = [a, b, 0.0, c, d, 0.0, e, f, 1.0]
            return
        raise TypeError(f"Unsupported Matrix constructor: {args!r}")

    # ---- factory helpers ------------------------------------------------
    @classmethod
    def _from_cos_array(cls, array: COSArray) -> Matrix:
        from pypdfbox.cos.cos_number import COSNumber

        single = [0.0] * SIZE
        single[0] = float(array.get_object(0).float_value())  # type: ignore[union-attr]
        single[1] = float(array.get_object(1).float_value())  # type: ignore[union-attr]
        single[3] = float(array.get_object(2).float_value())  # type: ignore[union-attr]
        single[4] = float(array.get_object(3).float_value())  # type: ignore[union-attr]
        single[6] = float(array.get_object(4).float_value())  # type: ignore[union-attr]
        single[7] = float(array.get_object(5).float_value())  # type: ignore[union-attr]
        single[8] = 1.0
        _ = COSNumber  # ensure import path mirrors upstream
        return cls(single)

    @staticmethod
    def create_matrix(base: COSBase | None) -> Matrix:
        """Build a Matrix from a six-number ``COSArray``, else identity."""
        from pypdfbox.cos.cos_array import COSArray
        from pypdfbox.cos.cos_number import COSNumber

        if not isinstance(base, COSArray):
            return Matrix()
        if base.size() < 6:
            return Matrix()
        for i in range(6):
            if not isinstance(base.get_object(i), COSNumber):
                return Matrix()
        return Matrix._from_cos_array(base)

    # ---- accessors -----------------------------------------------------
    def get_value(self, row: int, column: int) -> float:
        return self._single[row * 3 + column]

    def set_value(self, row: int, column: int, value: float) -> None:
        self._single[row * 3 + column] = float(value)

    def get_values(self) -> list[list[float]]:
        s = self._single
        return [
            [s[0], s[1], s[2]],
            [s[3], s[4], s[5]],
            [s[6], s[7], s[8]],
        ]

    # ---- core arithmetic ----------------------------------------------
    def concatenate(self, matrix: Matrix) -> None:
        self._single = _check_float_values(_multiply_arrays(matrix._single, self._single))

    def translate(self, x: float | Vector, y: float | None = None) -> None:
        if y is None:
            # Vector overload.
            tx, ty = x.get_x(), x.get_y()  # type: ignore[union-attr]
        else:
            tx, ty = float(x), float(y)  # type: ignore[arg-type]
        s = self._single
        s[6] += tx * s[0] + ty * s[3]
        s[7] += tx * s[1] + ty * s[4]
        s[8] += tx * s[2] + ty * s[5]
        _check_float_values(s)

    def scale(self, sx: float, sy: float) -> None:
        s = self._single
        s[0] *= sx
        s[1] *= sx
        s[2] *= sx
        s[3] *= sy
        s[4] *= sy
        s[5] *= sy
        _check_float_values(s)

    def rotate(self, theta: float) -> None:
        self.concatenate(Matrix.get_rotate_instance(theta, 0.0, 0.0))

    def multiply(self, other: Matrix) -> Matrix:
        return Matrix(_check_float_values(_multiply_arrays(self._single, other._single)))

    def transform_point(self, x: float, y: float) -> tuple[float, float]:
        s = self._single
        return (x * s[0] + y * s[3] + s[6], x * s[1] + y * s[4] + s[7])

    def transform(self, vector_or_point: Vector | tuple[float, float] | object) -> object:
        from pypdfbox.util.vector import Vector

        if isinstance(vector_or_point, Vector):
            x = vector_or_point.get_x()
            y = vector_or_point.get_y()
            nx, ny = self.transform_point(x, y)
            return Vector(nx, ny)
        if isinstance(vector_or_point, tuple) and len(vector_or_point) == 2:
            return self.transform_point(*vector_or_point)
        # Mutate a Point2D-like object with set_location.
        obj = vector_or_point
        x = float(obj.get_x())  # type: ignore[union-attr]
        y = float(obj.get_y())  # type: ignore[union-attr]
        nx, ny = self.transform_point(x, y)
        obj.set_location(nx, ny)  # type: ignore[union-attr]
        return None

    # ---- factory statics ----------------------------------------------
    @staticmethod
    def get_scale_instance(x: float, y: float) -> Matrix:
        return Matrix(x, 0.0, 0.0, y, 0.0, 0.0)

    @staticmethod
    def get_translate_instance(x: float, y: float) -> Matrix:
        return Matrix(1.0, 0.0, 0.0, 1.0, x, y)

    @staticmethod
    def get_rotate_instance(theta: float, tx: float, ty: float) -> Matrix:
        c = math.cos(theta)
        s = math.sin(theta)
        return Matrix(c, s, -s, c, tx, ty)

    @staticmethod
    def concatenate_matrices(a: Matrix, b: Matrix) -> Matrix:
        """Mirror upstream's static ``Matrix.concatenate(a, b)``."""
        return b.multiply(a)

    def clone(self) -> Matrix:
        return Matrix(list(self._single))

    # ---- scaling/translation extractors ------------------------------
    def get_scaling_factor_x(self) -> float:
        if self._single[1] != 0.0:
            return math.sqrt(self._single[0] ** 2 + self._single[1] ** 2)
        return self._single[0]

    def get_scaling_factor_y(self) -> float:
        if self._single[3] != 0.0:
            return math.sqrt(self._single[3] ** 2 + self._single[4] ** 2)
        return self._single[4]

    def get_scale_x(self) -> float:
        return self._single[0]

    def get_shear_y(self) -> float:
        return self._single[1]

    def get_shear_x(self) -> float:
        return self._single[3]

    def get_scale_y(self) -> float:
        return self._single[4]

    def get_translate_x(self) -> float:
        return self._single[6]

    def get_translate_y(self) -> float:
        return self._single[7]

    def to_cos_array(self) -> COSArray:
        from pypdfbox.cos.cos_array import COSArray
        from pypdfbox.cos.cos_float import COSFloat

        array = COSArray()
        array.add(COSFloat(self._single[0]))
        array.add(COSFloat(self._single[1]))
        array.add(COSFloat(self._single[3]))
        array.add(COSFloat(self._single[4]))
        array.add(COSFloat(self._single[6]))
        array.add(COSFloat(self._single[7]))
        return array

    # ---- equality / hashing ------------------------------------------
    def __repr__(self) -> str:
        s = self._single
        return f"[{s[0]},{s[1]},{s[3]},{s[4]},{s[6]},{s[7]}]"

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, Matrix):
            return False
        return self._single == other._single

    def __hash__(self) -> int:
        return hash(tuple(self._single))

    # ---- upstream parity surface -------------------------------------
    def equals(self, obj: object) -> bool:
        """Mirror of ``Matrix.equals`` (Java line 597)."""
        return self.__eq__(obj)

    def hash_code(self) -> int:
        """Mirror of ``Matrix.hashCode`` (Java line 591)."""
        return self.__hash__()

    def to_string(self) -> str:
        """Mirror of ``Matrix.toString`` (Java line 579)."""
        return self.__repr__()

    def create_affine_transform(self) -> tuple[float, float, float, float, float, float]:
        """Mirror of ``Matrix.createAffineTransform`` (Java line 169).

        Returns the six floats ``(sx, hy, hx, sy, tx, ty)`` in the order
        used by ``java.awt.geom.AffineTransform``.
        """
        s = self._single
        return (s[0], s[1], s[3], s[4], s[6], s[7])

    @staticmethod
    def check_float_values(values: list[float]) -> list[float]:
        """Mirror of ``Matrix.checkFloatValues`` (Java line 295)."""
        return _check_float_values(values)

    @staticmethod
    def multiply_arrays(a: list[float], b: list[float]) -> list[float]:
        """Mirror of ``Matrix.multiplyArrays`` (Java line 304)."""
        return _multiply_arrays(a, b)


__all__ = ["Matrix"]
