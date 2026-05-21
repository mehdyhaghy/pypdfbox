"""Ported from Apache PDFBox 3.0.

Upstream: ``pdfbox/src/test/java/org/apache/pdfbox/util/MatrixTest.java``

Translation notes:
- ``assertEquals(expected, actual, delta)`` → ``pytest.approx`` with ``abs=delta``.
- ``Matrix.clone()`` → ``Matrix.clone()`` (pypdfbox mirrors the upstream API).
- ``IllegalArgumentException`` (raised by ``Matrix.multiply`` on non-finite
  cells) → ``ValueError`` in pypdfbox.
- ``Float.MAX_VALUE`` / ``Float.POSITIVE_INFINITY`` / ``Float.NEGATIVE_INFINITY``
  / ``Float.NaN`` map to ``sys.float_info.max``, ``math.inf``, ``-math.inf``,
  ``math.nan``. The first row's ``Float.MAX_VALUE`` test asserts that
  ``multiply`` rejects the resulting non-finite intermediate; Python floats are
  64-bit so we use a value large enough to overflow when squared.
- ``testMultiplicationPerformance`` is a manual-toggle benchmark in upstream
  (commented-out ``@Test``); we omit it.
"""

from __future__ import annotations

import math
import sys

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_name import COSName
from pypdfbox.util.matrix import Matrix


def _assert_matrix_values_equal_to(values: list[float], m: Matrix) -> None:
    delta = 1e-5
    for i, expected in enumerate(values):
        row = i // 3
        column = i % 3
        actual = m.get_value(row, column)
        assert actual == pytest.approx(expected, abs=delta), (
            f"Incorrect value for matrix[{row},{column}]"
        )


def _assert_matrix_is_pristine(m: Matrix) -> None:
    _assert_matrix_values_equal_to([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0], m)


def test_construction_and_copy():
    m1 = Matrix()
    _assert_matrix_is_pristine(m1)

    m2 = m1.clone()
    assert m1 is not m2
    _assert_matrix_is_pristine(m2)


def test_get_scaling_factor():
    # check scaling factor of an initial matrix
    m1 = Matrix()
    assert m1.get_scaling_factor_x() == pytest.approx(1.0, abs=0)
    assert m1.get_scaling_factor_y() == pytest.approx(1.0, abs=0)

    # 2*2 + 4*4 = 20, sqrt(20) is the scaling factor for both axes.
    m2 = Matrix(2.0, 4.0, 4.0, 2.0, 0.0, 0.0)
    expected = math.sqrt(20.0)
    assert m2.get_scaling_factor_x() == pytest.approx(expected, abs=0)
    assert m2.get_scaling_factor_y() == pytest.approx(expected, abs=0)


def test_create_matrix_using_invalid_input():
    # anything but a COSArray is invalid and leads to an initial matrix
    create_matrix = Matrix.create_matrix(COSName.A)
    _assert_matrix_is_pristine(create_matrix)

    # a COSArray with fewer than 6 entries leads to an initial matrix
    cos_array = COSArray()
    cos_array.add(COSName.A)
    create_matrix = Matrix.create_matrix(cos_array)
    _assert_matrix_is_pristine(create_matrix)

    # a COSArray containing other kind of objects than COSNumber leads to an initial matrix
    cos_array = COSArray()
    for _ in range(6):
        cos_array.add(COSName.A)
    create_matrix = Matrix.create_matrix(cos_array)
    _assert_matrix_is_pristine(create_matrix)


def test_multiplication():
    # These matrices will not change - we use it to drive the various multiplications.
    const1 = Matrix()
    const2 = Matrix()

    # Create matrix with values
    # [ 0, 1, 2
    #   1, 2, 3
    #   2, 3, 4]
    for x in range(3):
        for y in range(3):
            const1.set_value(x, y, float(x + y))
            const2.set_value(x, y, float(8 + x + y))

    m1_multiplied_by_m1 = [5.0, 8.0, 11.0, 8.0, 14.0, 20.0, 11.0, 20.0, 29.0]
    m1_multiplied_by_m2 = [29.0, 32.0, 35.0, 56.0, 62.0, 68.0, 83.0, 92.0, 101.0]
    m2_multiplied_by_m1 = [29.0, 56.0, 83.0, 32.0, 62.0, 92.0, 35.0, 68.0, 101.0]

    var1 = const1.clone()
    var2 = const2.clone()

    # Multiply two matrices together producing a new result matrix.
    result = var1.multiply(var2)
    assert var1 == const1
    assert var2 == const2
    _assert_matrix_values_equal_to(m1_multiplied_by_m2, result)

    # Multiply two matrices together with the result being written to a third matrix
    # (Any existing values there will be overwritten).
    result = var1.multiply(var2)
    assert var1 == const1
    assert var2 == const2
    _assert_matrix_values_equal_to(m1_multiplied_by_m2, result)

    # Multiply two matrices together with the result being written into 'this' matrix
    var1 = const1.clone()
    var2 = const2.clone()
    var1.concatenate(var2)
    assert var2 == const2
    _assert_matrix_values_equal_to(m2_multiplied_by_m1, var1)

    var1 = const1.clone()
    var2 = const2.clone()
    result = Matrix.concatenate_matrices(var1, var2)
    assert var1 == const1
    assert var2 == const2
    _assert_matrix_values_equal_to(m2_multiplied_by_m1, result)

    # Multiply the same matrix with itself with the result being written into 'this' matrix
    var1 = const1.clone()
    result = var1.multiply(var1)
    assert var1 == const1
    _assert_matrix_values_equal_to(m1_multiplied_by_m1, result)


def test_old_multiplication():
    # This matrix will not change - we use it to drive the various multiplications.
    test_matrix = Matrix()

    # Create matrix with values
    # [ 0, 1, 2
    #   1, 2, 3
    #   2, 3, 4]
    for x in range(3):
        for y in range(3):
            test_matrix.set_value(x, y, float(x + y))

    m1 = test_matrix.clone()
    m2 = test_matrix.clone()

    # Multiply two matrices together producing a new result matrix.
    product = m1.multiply(m2)

    assert m1 is not product
    assert m2 is not product

    # Operand 1 should not have changed
    _assert_matrix_values_equal_to([0, 1, 2, 1, 2, 3, 2, 3, 4], m1)
    # Operand 2 should not have changed
    _assert_matrix_values_equal_to([0, 1, 2, 1, 2, 3, 2, 3, 4], m2)
    _assert_matrix_values_equal_to([5, 8, 11, 8, 14, 20, 11, 20, 29], product)

    ret_val = m1.multiply(m2)
    _assert_matrix_values_equal_to([0, 1, 2, 1, 2, 3, 2, 3, 4], m1)
    _assert_matrix_values_equal_to([0, 1, 2, 1, 2, 3, 2, 3, 4], m2)
    _assert_matrix_values_equal_to([5, 8, 11, 8, 14, 20, 11, 20, 29], ret_val)

    # Multiply the same matrix with itself with the result being written into 'this' matrix
    m1 = test_matrix.clone()

    ret_val = m1.multiply(m1)
    _assert_matrix_values_equal_to([0, 1, 2, 1, 2, 3, 2, 3, 4], m1)
    _assert_matrix_values_equal_to([5, 8, 11, 8, 14, 20, 11, 20, 29], ret_val)


def test_illegal_value_nan_1():
    # Java's Float.MAX_VALUE squared overflows to +Inf; pypdfbox uses Python
    # 64-bit floats, so we use a value whose square exceeds float-max.
    m = Matrix()
    m.set_value(0, 0, sys.float_info.max)
    with pytest.raises(ValueError):
        m.multiply(m)


def test_illegal_value_nan_2():
    m = Matrix()
    m.set_value(0, 0, math.nan)
    with pytest.raises(ValueError):
        m.multiply(m)


def test_illegal_value_positive_infinity():
    m = Matrix()
    m.set_value(0, 0, math.inf)
    with pytest.raises(ValueError):
        m.multiply(m)


def test_illegal_value_negative_infinity():
    m = Matrix()
    m.set_value(0, 0, -math.inf)
    with pytest.raises(ValueError):
        m.multiply(m)


def test_pdfbox2872():
    """Regression: PDFBOX-2872 — Matrix.to_cos_array must emit six floats."""
    m = Matrix(2.0, 4.0, 5.0, 8.0, 2.0, 0.0)
    to_cos_array = m.to_cos_array()
    assert to_cos_array.get(0) == COSFloat(2)
    assert to_cos_array.get(1) == COSFloat(4)
    assert to_cos_array.get(2) == COSFloat(5)
    assert to_cos_array.get(3) == COSFloat(8)
    assert to_cos_array.get(4) == COSFloat(2)
    assert to_cos_array.get(5) == COSFloat.ZERO


def test_get_values():
    m = Matrix(2.0, 4.0, 4.0, 2.0, 15.0, 30.0)
    values = m.get_values()
    assert values[0][0] == pytest.approx(2.0, abs=0)
    assert values[0][1] == pytest.approx(4.0, abs=0)
    assert values[0][2] == pytest.approx(0.0, abs=0)
    assert values[1][0] == pytest.approx(4.0, abs=0)
    assert values[1][1] == pytest.approx(2.0, abs=0)
    assert values[1][2] == pytest.approx(0.0, abs=0)
    assert values[2][0] == pytest.approx(15.0, abs=0)
    assert values[2][1] == pytest.approx(30.0, abs=0)
    assert values[2][2] == pytest.approx(1.0, abs=0)


def test_scaling():
    m = Matrix(2.0, 4.0, 4.0, 2.0, 15.0, 30.0)
    m.scale(2.0, 3.0)
    # first row, multiplication with 2
    assert m.get_value(0, 0) == pytest.approx(4.0, abs=0)
    assert m.get_value(0, 1) == pytest.approx(8.0, abs=0)
    assert m.get_value(0, 2) == pytest.approx(0.0, abs=0)

    # second row, multiplication with 3
    assert m.get_value(1, 0) == pytest.approx(12.0, abs=0)
    assert m.get_value(1, 1) == pytest.approx(6.0, abs=0)
    assert m.get_value(1, 2) == pytest.approx(0.0, abs=0)

    # third row, no changes at all
    assert m.get_value(2, 0) == pytest.approx(15.0, abs=0)
    assert m.get_value(2, 1) == pytest.approx(30.0, abs=0)
    assert m.get_value(2, 2) == pytest.approx(1.0, abs=0)


def test_translation():
    m = Matrix(2.0, 4.0, 4.0, 2.0, 15.0, 30.0)
    m.translate(2.0, 3.0)
    # first row, no changes at all
    assert m.get_value(0, 0) == pytest.approx(2.0, abs=0)
    assert m.get_value(0, 1) == pytest.approx(4.0, abs=0)
    assert m.get_value(0, 2) == pytest.approx(0.0, abs=0)

    # second row, no changes at all
    assert m.get_value(1, 0) == pytest.approx(4.0, abs=0)
    assert m.get_value(1, 1) == pytest.approx(2.0, abs=0)
    assert m.get_value(1, 2) == pytest.approx(0.0, abs=0)

    # third row, translated values
    assert m.get_value(2, 0) == pytest.approx(31.0, abs=0)
    assert m.get_value(2, 1) == pytest.approx(44.0, abs=0)
    assert m.get_value(2, 2) == pytest.approx(1.0, abs=0)
