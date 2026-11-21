"""Port of upstream ``CFFParserMatrixTest`` from
``fontbox/src/test/java/org/apache/fontbox/cff/CFFParserMatrixTest.java``
(PDFBOX-6324).

Tests the matrix concatenation used by ``CFFParser`` to combine the
FontMatrix of the top DICT with the FontMatrix of a Font DICT of a CID
keyed font. Matrices are ``[a b c d x y]`` and are concatenated as row
vector transformations: ``dest = dest x concat``.

The upstream ``AffineTransform`` cross-check is translated to an
independent 3x3 matrix product (``java.awt.geom`` has no Python
equivalent); the random seed differs from ``java.util.Random`` but the
property checked is the same.
"""

import random

import pytest

from pypdfbox.fontbox.cff.cff_parser import CFFParser

DELTA = 1e-12

_CASES = [
    # distinct values everywhere, so that every wrong operand changes the result
    ("general", [1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], [25, 28, 57, 64, 100, 112]),
    # b1 != 0 and d1 != d2: b must be a1*b2 + b1*d2 = 0.25 * 0.002
    (
        "skewed",
        [1, 0.25, 0, 1, 0, 0],
        [0.001, 0, 0, 0.002, 0, 0],
        [0.001, 0.0005, 0, 0.002, 0, 0],
    ),
    # same matrices in the opposite order: the operation is not commutative
    (
        "skewed, operands swapped",
        [0.001, 0, 0, 0.002, 0, 0],
        [1, 0.25, 0, 1, 0, 0],
        [0.001, 0.00025, 0, 0.002, 0, 0],
    ),
    # synthetic oblique (c != 0) combined with a different y scale
    (
        "oblique",
        [0.001, 0, 0.0002, 0.001, 0, 0],
        [1, 0, 0, 0.5, 0, 0],
        [0.001, 0, 0.0002, 0.0005, 0, 0],
    ),
    # identity must not change a matrix, including its skew and translation
    (
        "identity",
        [0.001, 0.0003, 0.0002, 0.001, 10, 20],
        [1, 0, 0, 1, 0, 0],
        [0.001, 0.0003, 0.0002, 0.001, 10, 20],
    ),
    # the translation of dest is transformed by concat, then its translation is
    # added: x = 3*2 + 4*(-1) + 5 = 7, y = 3*1 + 4*2 + 6 = 17
    ("translation", [1, 0, 0, 1, 3, 4], [2, 1, -1, 2, 5, 6], [2, 1, -1, 2, 7, 17]),
    # the usual case: no skew, both matrices only scale
    (
        "scale only",
        [0.001, 0, 0, 0.001, 0, 0],
        [2, 0, 0, 3, 0, 0],
        [0.002, 0, 0, 0.003, 0, 0],
    ),
]


def _assert_matrix(expected: list[float], found: list[float]) -> None:
    assert len(found) == len(expected), "unexpected matrix size"
    for e, f in zip(expected, found, strict=True):
        assert float(f) == pytest.approx(e, abs=DELTA), f"unexpected matrix {found}"


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [c[1:] for c in _CASES],
    ids=[c[0] for c in _CASES],
)
def test_concatenate_matrix(
    first: list[float], second: list[float], expected: list[float]
) -> None:
    dest = [float(v) for v in first]
    concat = [float(v) for v in second]

    CFFParser().concatenate_matrix(dest, concat)

    _assert_matrix(expected, dest)
    # only the first matrix is changed
    _assert_matrix(second, concat)


def _reference(first: list[float], second: list[float]) -> list[float]:
    """``first`` then ``second`` via a plain 3x3 product (row vectors)."""

    def to3(m: list[float]) -> list[list[float]]:
        return [[m[0], m[1], 0.0], [m[2], m[3], 0.0], [m[4], m[5], 1.0]]

    a, b = to3(first), to3(second)
    p = [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return [p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1]]


def test_concatenate_matrix_matches_affine_transform() -> None:
    rng = random.Random(4711)
    for _ in range(1000):
        first = [rng.random() * 20 - 10 for _ in range(6)]
        second = [rng.random() * 20 - 10 for _ in range(6)]
        dest = list(first)
        CFFParser().concatenate_matrix(dest, list(second))
        for e, f in zip(_reference(first, second), dest, strict=True):
            assert f == pytest.approx(e, abs=1e-9)


def test_concatenate_matrix_with_mixed_operand_types() -> None:
    """DICT operands are int or float depending on their encoding, so the
    result must not depend on the operand type."""
    dest: list = [2, 1, 0, 3, 0, 0]
    concat: list = [0.5, 0, 0, 0.5, 0, 0]

    CFFParser().concatenate_matrix(dest, concat)

    _assert_matrix([1, 0.5, 0, 1.5, 0, 0], dest)
