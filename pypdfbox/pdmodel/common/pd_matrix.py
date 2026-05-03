from __future__ import annotations

import math
from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSFloat, COSNumber


class PDMatrix:
    """
    A 3x3 transformation matrix used by content streams. Mirrors
    ``org.apache.pdfbox.util.Matrix``; placed under
    ``pypdfbox.pdmodel.common`` for callers that work with page-level
    matrices (CTM, text matrix, form XObject matrix, annotation
    appearance matrix) without reaching into ``pypdfbox.util``.

    Layout (column-major in upstream's flat array):

    ::

        a  b  0     single[0] single[1] single[2]
        c  d  0  =  single[3] single[4] single[5]
        e  f  1     single[6] single[7] single[8]

    where ``a``/``d`` are the X/Y scale, ``b``/``c`` are the shear
    components, and ``e``/``f`` are the X/Y translation. The third
    column is fixed to ``[0, 0, 1]`` for proper PDF matrices.

    The default constructor produces the identity matrix; the 6-float
    constructor populates a/b/c/d/e/f with the third column fixed to
    ``[0, 0, 1]``.
    """

    SIZE = 9

    __slots__ = ("_single",)

    def __init__(
        self,
        a: float | None = None,
        b: float = 0.0,
        c: float = 0.0,
        d: float = 0.0,
        e: float = 0.0,
        f: float = 0.0,
    ) -> None:
        """Construct a PDMatrix.

        ``PDMatrix()`` produces the identity matrix (matches upstream
        no-arg constructor). ``PDMatrix(a, b, c, d, e, f)`` produces a
        proper PDF transformation matrix with the supplied first two
        columns and the third column fixed to ``[0, 0, 1]``.
        """
        if a is None:
            self._single = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        else:
            self._single = [
                float(a), float(b), 0.0,
                float(c), float(d), 0.0,
                float(e), float(f), 1.0,
            ]

    # ---------- factories ----------

    @staticmethod
    def create_matrix(base: COSBase | None) -> PDMatrix:
        """Create a matrix from a possibly-untrustworthy COS object.

        Returns the identity matrix when ``base`` is not a ``COSArray``,
        or has fewer than 6 entries, or any of the first 6 entries is
        not a ``COSNumber``. Mirrors upstream ``Matrix.createMatrix``.
        """
        if not isinstance(base, COSArray):
            return PDMatrix()
        if base.size() < 6:
            return PDMatrix()
        for i in range(6):
            if not isinstance(base.get_object(i), COSNumber):
                return PDMatrix()
        return PDMatrix._from_cos_array(base)

    @staticmethod
    def _from_cos_array(array: COSArray) -> PDMatrix:
        """Internal: build a PDMatrix from a validated 6-element
        ``COSArray`` of ``COSNumber``s."""
        get_num = lambda i: array.get_object(i).float_value()  # noqa: E731
        return PDMatrix(
            get_num(0),
            get_num(1),
            get_num(2),
            get_num(3),
            get_num(4),
            get_num(5),
        )

    @staticmethod
    def get_scale_instance(x: float, y: float) -> PDMatrix:
        """Return a pure-scale matrix.

        ::

            x  0  0
            0  y  0
            0  0  1
        """
        return PDMatrix(x, 0.0, 0.0, y, 0.0, 0.0)

    @staticmethod
    def get_translate_instance(x: float, y: float) -> PDMatrix:
        """Return a pure-translate matrix.

        ::

            1  0  0
            0  1  0
            x  y  1
        """
        return PDMatrix(1.0, 0.0, 0.0, 1.0, x, y)

    @staticmethod
    def get_rotate_instance(theta: float, tx: float, ty: float) -> PDMatrix:
        """Return a rotate-then-translate matrix.

        ``theta`` is measured in radians.
        """
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        return PDMatrix(
            cos_theta,
            sin_theta,
            -sin_theta,
            cos_theta,
            tx,
            ty,
        )

    # ---------- raw element access ----------

    def get_value(self, row: int, column: int) -> float:
        """Return the entry at ``(row, column)`` (0-indexed, row-major
        within the flat 3x3 storage)."""
        return self._single[row * 3 + column]

    def set_value(self, row: int, column: int, value: float) -> None:
        """Replace the entry at ``(row, column)``."""
        self._single[row * 3 + column] = float(value)

    def get_values(self) -> list[list[float]]:
        """Return the 3x3 matrix as a fresh ``list[list[float]]``.

        Modifying the returned structure does not mutate the matrix —
        upstream ``getValues()`` returns a fresh ``float[][]`` and we
        match that defensive-copy semantic.
        """
        s = self._single
        return [
            [s[0], s[1], s[2]],
            [s[3], s[4], s[5]],
            [s[6], s[7], s[8]],
        ]

    # ---------- typed component accessors ----------

    def get_scale_x(self) -> float:
        """Return the x-scaling element ``a`` (entry at row 0, col 0)."""
        return self._single[0]

    def get_shear_y(self) -> float:
        """Return the y-shear element ``b`` (entry at row 0, col 1)."""
        return self._single[1]

    def get_shear_x(self) -> float:
        """Return the x-shear element ``c`` (entry at row 1, col 0)."""
        return self._single[3]

    def get_scale_y(self) -> float:
        """Return the y-scaling element ``d`` (entry at row 1, col 1)."""
        return self._single[4]

    def get_translate_x(self) -> float:
        """Return the x-translation element ``e`` (entry at row 2, col 0)."""
        return self._single[6]

    def get_translate_y(self) -> float:
        """Return the y-translation element ``f`` (entry at row 2, col 1)."""
        return self._single[7]

    def get_scaling_factor_x(self) -> float:
        """Return the effective x-scaling factor.

        When the matrix is rotated (the y-shear element is non-zero),
        this is ``sqrt(a^2 + b^2)``; otherwise it is just ``a``. Mirrors
        upstream ``getScalingFactorX()``.
        """
        if self._single[1] != 0.0:
            return math.sqrt(self._single[0] ** 2 + self._single[1] ** 2)
        return self._single[0]

    def get_scaling_factor_y(self) -> float:
        """Return the effective y-scaling factor.

        When the matrix is rotated (the x-shear element is non-zero),
        this is ``sqrt(c^2 + d^2)``; otherwise it is just ``d``.
        """
        if self._single[3] != 0.0:
            return math.sqrt(self._single[3] ** 2 + self._single[4] ** 2)
        return self._single[4]

    # ---------- mutation ----------

    def concatenate(self, other: PDMatrix) -> None:
        """Pre-multiply this matrix by ``other`` in place.

        After ``self.concatenate(other)``, ``self`` is replaced with
        ``other * self`` (the geometric meaning being: apply ``self``
        first, then ``other``).
        """
        self._single = self._check_finite(
            self._multiply_arrays(other._single, self._single)
        )

    def translate(self, tx: float, ty: float) -> None:
        """Translate this matrix in place by ``(tx, ty)``."""
        s = self._single
        s[6] += tx * s[0] + ty * s[3]
        s[7] += tx * s[1] + ty * s[4]
        s[8] += tx * s[2] + ty * s[5]
        self._check_finite(s)

    def scale(self, sx: float, sy: float) -> None:
        """Scale this matrix in place by ``(sx, sy)``.

        Note that upstream ``scale`` only multiplies the first two rows
        by ``sx`` and ``sy`` respectively (it leaves the translation
        row untouched). This pypdfbox port preserves that exact
        semantic.
        """
        s = self._single
        s[0] *= sx
        s[1] *= sx
        s[2] *= sx
        s[3] *= sy
        s[4] *= sy
        s[5] *= sy
        self._check_finite(s)

    def rotate(self, theta: float) -> None:
        """Rotate this matrix in place by ``theta`` radians (about the
        origin)."""
        self.concatenate(PDMatrix.get_rotate_instance(theta, 0.0, 0.0))

    # ---------- multiplication ----------

    def multiply(self, other: PDMatrix) -> PDMatrix:
        """Return ``self * other`` as a fresh matrix.

        Neither operand is modified. Aliasing is allowed:
        ``m.multiply(m)`` is well-defined.
        """
        return PDMatrix._from_array(
            self._check_finite(self._multiply_arrays(self._single, other._single))
        )

    @staticmethod
    def concatenate_matrices(a: PDMatrix, b: PDMatrix) -> PDMatrix:
        """Return ``b * a`` as a fresh matrix.

        Mirrors upstream ``Matrix.concatenate(a, b)`` (a static helper
        whose semantic is ``b.multiply(a)``). pypdfbox renames the
        static form to ``concatenate_matrices`` so it does not collide
        with the instance method :meth:`concatenate`.
        """
        return b.multiply(a)

    @classmethod
    def _from_array(cls, src: list[float]) -> PDMatrix:
        """Internal constructor that adopts an existing 9-element array
        without copying. Mirrors upstream's private array constructor.
        """
        m = cls.__new__(cls)
        m._single = src
        return m

    @staticmethod
    def _multiply_arrays(a: list[float], b: list[float]) -> list[float]:
        """3x3 matrix product over flat 9-element arrays."""
        c = [0.0] * 9
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

    @staticmethod
    def _check_finite(values: list[float]) -> list[float]:
        """Raise ``ValueError`` if any element is non-finite. Mirrors
        upstream ``checkFloatValues`` (which throws
        ``IllegalArgumentException``)."""
        for v in values:
            if not math.isfinite(v):
                raise ValueError("Multiplying two matrices produces illegal values")
        return values

    # ---------- point / vector transforms ----------

    def transform_point(self, x: float, y: float) -> tuple[float, float]:
        """Transform a 2D point by this matrix and return the resulting
        ``(x, y)`` tuple. Mirrors upstream ``transformPoint``.
        """
        s = self._single
        a = s[0]
        b = s[1]
        c = s[3]
        d = s[4]
        e = s[6]
        f = s[7]
        return (x * a + y * c + e, x * b + y * d + f)

    # ---------- predicates / convenience ----------

    def is_identity(self) -> bool:
        """Return ``True`` when this matrix is exactly the identity.

        pypdfbox extension — upstream callers compare element-by-element
        or rely on object identity. Surfaced here as a fast-path check
        for callers that elide identity matrices in CTM serialisation
        and appearance-stream generation.
        """
        s = self._single
        return (
            s[0] == 1.0 and s[1] == 0.0 and s[2] == 0.0
            and s[3] == 0.0 and s[4] == 1.0 and s[5] == 0.0
            and s[6] == 0.0 and s[7] == 0.0 and s[8] == 1.0
        )

    def get_single(self) -> list[float]:
        """Return a copy of the flat 9-element array.

        pypdfbox extension — upstream's ``single`` array is private. A
        copy (not a view) is returned to preserve the encapsulation
        guarantee that callers cannot mutate the matrix through this
        accessor.
        """
        return list(self._single)

    # ---------- COS surface ----------

    def to_cos_array(self) -> COSArray:
        """Serialise the geometric components (a, b, c, d, e, f) to a
        6-element ``COSArray``. The third column ``[0, 0, 1]`` is
        intentionally omitted — that is the canonical PDF form for a
        transformation matrix.
        """
        s = self._single
        array = COSArray()
        array.add(COSFloat(s[0]))
        array.add(COSFloat(s[1]))
        array.add(COSFloat(s[3]))
        array.add(COSFloat(s[4]))
        array.add(COSFloat(s[6]))
        array.add(COSFloat(s[7]))
        return array

    # ---------- copy / equality / debug ----------

    def clone(self) -> PDMatrix:
        """Return a deep copy of this matrix."""
        return PDMatrix._from_array(list(self._single))

    def __copy__(self) -> PDMatrix:
        return self.clone()

    def __deepcopy__(self, memo: dict[int, Any]) -> PDMatrix:
        return self.clone()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PDMatrix):
            return NotImplemented
        return self._single == other._single

    def __hash__(self) -> int:
        return hash(tuple(self._single))

    def __str__(self) -> str:
        s = self._single
        return (
            "["
            + str(s[0]) + ","
            + str(s[1]) + ","
            + str(s[3]) + ","
            + str(s[4]) + ","
            + str(s[6]) + ","
            + str(s[7])
            + "]"
        )

    def __repr__(self) -> str:
        s = self._single
        return (
            f"PDMatrix(a={s[0]!r}, b={s[1]!r}, c={s[3]!r}, "
            f"d={s[4]!r}, e={s[6]!r}, f={s[7]!r})"
        )


__all__ = ["PDMatrix"]
