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
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.cos.cos_array import COSArray
    from pypdfbox.cos.cos_base import COSBase
    from pypdfbox.util.vector import Vector

SIZE = 9

_PACK_F32 = struct.Struct(">f").pack
_UNPACK_F32 = struct.Struct(">f").unpack


def f32(value: float) -> float:
    """Narrow ``value`` to IEEE-754 single precision, as Java ``(float)`` does.

    Upstream ``Matrix`` stores its cells in a ``float[]`` (32-bit), so every
    value written to the matrix — and every intermediate in the float-typed
    arithmetic of ``multiplyArrays`` / ``transformPoint`` / ``translate`` /
    ``scale`` — is single precision. pypdfbox keeps Python ``float`` (64-bit)
    objects but rounds each store/operation to the nearest float32 so the
    matrix's observable element values match Apache PDFBox bit-for-bit (see the
    ``MatrixFloat32Probe`` oracle).

    A finite double whose magnitude rounds beyond ``Float.MAX_VALUE`` becomes a
    signed infinity in single precision (Java ``(float)`` cast); ``struct.pack``
    refuses to encode it, so synthesise the infinity. ``checkFloatValues`` then
    rejects it exactly as upstream does.
    """
    if math.isnan(value) or math.isinf(value):
        return value
    try:
        return _UNPACK_F32(_PACK_F32(value))[0]
    except OverflowError:
        return math.inf if value > 0 else -math.inf


def _float_compare_nonzero(value: float) -> bool:
    """True when ``Float.compare(value, 0.0f) != 0`` in Java.

    ``Float.compare`` distinguishes ``-0.0`` from ``+0.0`` (returns ``-1`` for
    ``-0.0``) and orders ``NaN`` above everything, so the only value that
    compares *equal* to ``+0.0`` is ``+0.0`` itself. The cheap ``value != 0.0``
    test would wrongly fold ``-0.0`` into the zero branch.
    """
    if value == 0.0:
        # +0.0 == -0.0 in Python; copysign tells them apart.
        return math.copysign(1.0, value) < 0.0
    return True


def _is_finite(values: list[float]) -> bool:
    return all(math.isfinite(v) for v in values)


def _check_float_values(values: list[float]) -> list[float]:
    if not _is_finite(values):
        raise ValueError("Multiplying two matrices produces illegal values")
    return values


def _multiply_arrays(a: list[float], b: list[float]) -> list[float]:
    # Java evaluates each cell in float arithmetic (float*float and float+float
    # both yield float), left-to-right, so every product and partial sum is
    # narrowed to single precision. Mirror that exactly with f32() on each step.
    def cell(i0: int, j0: int, i1: int, j1: int, i2: int, j2: int) -> float:
        s = f32(f32(a[i0] * b[j0]) + f32(a[i1] * b[j1]))
        return f32(s + f32(a[i2] * b[j2]))

    c = [0.0] * SIZE
    c[0] = cell(0, 0, 1, 3, 2, 6)
    c[1] = cell(0, 1, 1, 4, 2, 7)
    c[2] = cell(0, 2, 1, 5, 2, 8)
    c[3] = cell(3, 0, 4, 3, 5, 6)
    c[4] = cell(3, 1, 4, 4, 5, 7)
    c[5] = cell(3, 2, 4, 5, 5, 8)
    c[6] = cell(6, 0, 7, 3, 8, 6)
    c[7] = cell(6, 1, 7, 4, 8, 7)
    c[8] = cell(6, 2, 7, 5, 8, 8)
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
            a, b, c, d, e, f = (f32(v) for v in args)
            self._single = [a, b, 0.0, c, d, 0.0, e, f, 1.0]
            return
        raise TypeError(f"Unsupported Matrix constructor: {args!r}")

    # ---- factory helpers ------------------------------------------------
    @classmethod
    def _from_cos_array(cls, array: COSArray) -> Matrix:
        from pypdfbox.cos.cos_number import COSNumber

        # COSNumber.floatValue() already returns a Java float (32-bit); narrow
        # to match before storing into the float[] cells.
        single = [0.0] * SIZE
        single[0] = f32(array.get_object(0).float_value())  # type: ignore[union-attr]
        single[1] = f32(array.get_object(1).float_value())  # type: ignore[union-attr]
        single[3] = f32(array.get_object(2).float_value())  # type: ignore[union-attr]
        single[4] = f32(array.get_object(3).float_value())  # type: ignore[union-attr]
        single[6] = f32(array.get_object(4).float_value())  # type: ignore[union-attr]
        single[7] = f32(array.get_object(5).float_value())  # type: ignore[union-attr]
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
        self._single[row * 3 + column] = f32(value)

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
            # Vector overload (Vector components are already float32).
            tx, ty = x.get_x(), x.get_y()  # type: ignore[union-attr]
        else:
            tx, ty = f32(x), f32(y)  # type: ignore[arg-type]
        s = self._single
        # Java float arithmetic: each product and the running sum is single
        # precision (single[6] += tx*single[0] + ty*single[3]).
        s[6] = f32(s[6] + f32(f32(tx * s[0]) + f32(ty * s[3])))
        s[7] = f32(s[7] + f32(f32(tx * s[1]) + f32(ty * s[4])))
        s[8] = f32(s[8] + f32(f32(tx * s[2]) + f32(ty * s[5])))
        _check_float_values(s)

    def scale(self, sx: float, sy: float) -> None:
        s = self._single
        sx, sy = f32(sx), f32(sy)
        s[0] = f32(s[0] * sx)
        s[1] = f32(s[1] * sx)
        s[2] = f32(s[2] * sx)
        s[3] = f32(s[3] * sy)
        s[4] = f32(s[4] * sy)
        s[5] = f32(s[5] * sy)
        _check_float_values(s)

    def rotate(self, theta: float) -> None:
        self.concatenate(Matrix.get_rotate_instance(theta, 0.0, 0.0))

    def multiply(self, other: Matrix) -> Matrix:
        return Matrix(_check_float_values(_multiply_arrays(self._single, other._single)))

    def transform_point(self, x: float, y: float) -> tuple[float, float]:
        # Java narrows the inputs to float and evaluates in float arithmetic;
        # the result is a Point2D.Float (single precision).
        s = self._single
        x, y = f32(x), f32(y)
        nx = f32(f32(f32(x * s[0]) + f32(y * s[3])) + s[6])
        ny = f32(f32(f32(x * s[1]) + f32(y * s[4])) + s[7])
        return (nx, ny)

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
        # Java narrows cos/sin to float before constructing; the Matrix ctor
        # would narrow anyway, but the negation -sinTheta must operate on the
        # already-narrowed value to match upstream bit-for-bit.
        cos_theta = f32(math.cos(theta))
        sin_theta = f32(math.sin(theta))
        return Matrix(cos_theta, sin_theta, -sin_theta, cos_theta, tx, ty)

    @staticmethod
    def concatenate_matrices(a: Matrix, b: Matrix) -> Matrix:
        """Mirror upstream's static ``Matrix.concatenate(a, b)``."""
        return b.multiply(a)

    def clone(self) -> Matrix:
        return Matrix(list(self._single))

    # ---- scaling/translation extractors ------------------------------
    def get_scaling_factor_x(self) -> float:
        # Upstream uses Float.compare(single[1], 0.0f) != 0, which (unlike !=)
        # treats -0.0 as nonzero. The sqrt is computed in double (Math.pow
        # widens the float cells) then narrowed back to float on return.
        if _float_compare_nonzero(self._single[1]):
            return f32(math.sqrt(self._single[0] ** 2 + self._single[1] ** 2))
        return self._single[0]

    def get_scaling_factor_y(self) -> float:
        if _float_compare_nonzero(self._single[3]):
            return f32(math.sqrt(self._single[3] ** 2 + self._single[4] ** 2))
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
        # Upstream toString concatenates the raw Float.toString of each cell, so
        # a narrowed value like 0.9950042f renders "0.9950042" (not Python's
        # float64 repr) and a cell outside [1e-3, 1e7) keeps Java's scientific
        # form (e.g. "1.0E8"). float_to_string is the raw Float.toString port;
        # format_float32 would instead strip E-notation to plain decimal (the
        # COSFloat PDF-serialization step) which Matrix.toString does not do.
        from pypdfbox.cos.cos_float import float_to_string

        s = self._single
        cells = (s[0], s[1], s[3], s[4], s[6], s[7])
        return "[" + ",".join(float_to_string(v) for v in cells) + "]"

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
