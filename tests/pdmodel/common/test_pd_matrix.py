"""Hand-written tests for ``pypdfbox.pdmodel.common.PDMatrix``.

These cover the API exercised in pypdfbox: construction (no-arg
identity, 6-float, factories), typed accessors, mutation
(translate/scale/rotate/concatenate), multiplication (in-place +
non-aliasing), point transforms, COS round-trip, error handling
(non-finite checks, invalid factory inputs), predicates, equality,
hashing, and copy semantics.
"""

from __future__ import annotations

import copy
import math

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.common import PDMatrix

# ---------- construction ----------


def test_default_constructor_is_identity():
    m = PDMatrix()
    assert m.is_identity()
    assert m.get_values() == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def test_six_float_constructor_populates_columns():
    m = PDMatrix(2, 4, 5, 8, 2, 0)
    assert m.get_value(0, 0) == 2.0
    assert m.get_value(0, 1) == 4.0
    assert m.get_value(0, 2) == 0.0
    assert m.get_value(1, 0) == 5.0
    assert m.get_value(1, 1) == 8.0
    assert m.get_value(1, 2) == 0.0
    assert m.get_value(2, 0) == 2.0
    assert m.get_value(2, 1) == 0.0
    assert m.get_value(2, 2) == 1.0


def test_six_float_constructor_coerces_int_to_float():
    m = PDMatrix(1, 2, 3, 4, 5, 6)
    assert all(isinstance(x, float) for row in m.get_values() for x in row)


# ---------- factories ----------


def test_get_scale_instance():
    m = PDMatrix.get_scale_instance(3.0, 5.0)
    assert m.get_scale_x() == 3.0
    assert m.get_scale_y() == 5.0
    assert m.get_shear_x() == 0.0
    assert m.get_shear_y() == 0.0
    assert m.get_translate_x() == 0.0
    assert m.get_translate_y() == 0.0


def test_get_translate_instance():
    m = PDMatrix.get_translate_instance(7.0, -2.0)
    assert m.get_scale_x() == 1.0
    assert m.get_scale_y() == 1.0
    assert m.get_shear_x() == 0.0
    assert m.get_shear_y() == 0.0
    assert m.get_translate_x() == 7.0
    assert m.get_translate_y() == -2.0


def test_get_rotate_instance_90_degrees():
    m = PDMatrix.get_rotate_instance(math.pi / 2.0, 10.0, 20.0)
    # cos(pi/2) ~ 0, sin(pi/2) = 1
    assert math.isclose(m.get_scale_x(), 0.0, abs_tol=1e-7)
    assert math.isclose(m.get_shear_y(), 1.0, abs_tol=1e-7)
    assert math.isclose(m.get_shear_x(), -1.0, abs_tol=1e-7)
    assert math.isclose(m.get_scale_y(), 0.0, abs_tol=1e-7)
    assert m.get_translate_x() == 10.0
    assert m.get_translate_y() == 20.0


# ---------- create_matrix factory ----------


def test_create_matrix_from_non_array_returns_identity():
    m = PDMatrix.create_matrix(COSName.A)
    assert m.is_identity()


def test_create_matrix_from_none_returns_identity():
    m = PDMatrix.create_matrix(None)
    assert m.is_identity()


def test_create_matrix_from_short_array_returns_identity():
    arr = COSArray()
    arr.add(COSFloat(1.0))
    arr.add(COSFloat(2.0))
    arr.add(COSFloat(3.0))
    m = PDMatrix.create_matrix(arr)
    assert m.is_identity()


def test_create_matrix_with_non_number_entry_returns_identity():
    arr = COSArray()
    for _ in range(6):
        arr.add(COSName.A)
    m = PDMatrix.create_matrix(arr)
    assert m.is_identity()


def test_create_matrix_with_six_numbers_populates():
    arr = COSArray()
    for v in (2.0, 4.0, 5.0, 8.0, 2.0, 0.0):
        arr.add(COSFloat(v))
    m = PDMatrix.create_matrix(arr)
    assert m.get_scale_x() == 2.0
    assert m.get_shear_y() == 4.0
    assert m.get_shear_x() == 5.0
    assert m.get_scale_y() == 8.0
    assert m.get_translate_x() == 2.0
    assert m.get_translate_y() == 0.0


def test_create_matrix_accepts_cos_integer_entries():
    arr = COSArray()
    for v in (1, 0, 0, 1, 5, 6):
        arr.add(COSInteger.get(v))
    m = PDMatrix.create_matrix(arr)
    assert m.get_translate_x() == 5.0
    assert m.get_translate_y() == 6.0


# ---------- typed component accessors ----------


def test_typed_accessors_return_expected_components():
    m = PDMatrix(2.5, 3.5, 4.5, 5.5, 6.5, 7.5)
    assert m.get_scale_x() == 2.5
    assert m.get_shear_y() == 3.5
    assert m.get_shear_x() == 4.5
    assert m.get_scale_y() == 5.5
    assert m.get_translate_x() == 6.5
    assert m.get_translate_y() == 7.5


def test_get_scaling_factor_x_no_shear():
    m = PDMatrix(3.0, 0.0, 0.0, 5.0, 0.0, 0.0)
    assert m.get_scaling_factor_x() == 3.0


def test_get_scaling_factor_x_with_shear_uses_pythagoras():
    m = PDMatrix(3.0, 4.0, 0.0, 1.0, 0.0, 0.0)
    assert math.isclose(m.get_scaling_factor_x(), 5.0)


def test_get_scaling_factor_y_no_shear():
    m = PDMatrix(1.0, 0.0, 0.0, 7.0, 0.0, 0.0)
    assert m.get_scaling_factor_y() == 7.0


def test_get_scaling_factor_y_with_shear_uses_pythagoras():
    m = PDMatrix(1.0, 0.0, 3.0, 4.0, 0.0, 0.0)
    assert math.isclose(m.get_scaling_factor_y(), 5.0)


# ---------- get/set value ----------


def test_set_value_updates_storage():
    m = PDMatrix()
    m.set_value(0, 1, 9.0)
    assert m.get_value(0, 1) == 9.0


def test_get_values_returns_defensive_copy():
    m = PDMatrix(2, 4, 5, 8, 2, 0)
    values = m.get_values()
    values[0][0] = 999.0
    assert m.get_value(0, 0) == 2.0


def test_get_single_returns_copy():
    m = PDMatrix(1, 2, 3, 4, 5, 6)
    s = m.get_single()
    s[0] = 999.0
    assert m.get_value(0, 0) == 1.0


# ---------- mutation: translate ----------


def test_translate_changes_only_translation_row_for_axis_aligned():
    m = PDMatrix(2, 4, 4, 2, 15, 30)
    m.translate(2, 3)
    # First row unchanged
    assert m.get_value(0, 0) == 2.0
    assert m.get_value(0, 1) == 4.0
    # Second row unchanged
    assert m.get_value(1, 0) == 4.0
    assert m.get_value(1, 1) == 2.0
    # Third row translated
    assert m.get_value(2, 0) == 31.0
    assert m.get_value(2, 1) == 44.0


# ---------- mutation: scale ----------


def test_scale_multiplies_first_two_rows():
    m = PDMatrix(2, 4, 4, 2, 15, 30)
    m.scale(2, 3)
    assert m.get_value(0, 0) == 4.0
    assert m.get_value(0, 1) == 8.0
    assert m.get_value(0, 2) == 0.0
    assert m.get_value(1, 0) == 12.0
    assert m.get_value(1, 1) == 6.0
    assert m.get_value(1, 2) == 0.0
    # Translation row untouched
    assert m.get_value(2, 0) == 15.0
    assert m.get_value(2, 1) == 30.0
    assert m.get_value(2, 2) == 1.0


# ---------- mutation: rotate ----------


def test_rotate_by_90_concatenates_rotation():
    m = PDMatrix()
    m.rotate(math.pi / 2.0)
    # Rotated identity should match the rotation matrix itself
    assert math.isclose(m.get_scale_x(), 0.0, abs_tol=1e-7)
    assert math.isclose(m.get_shear_y(), 1.0, abs_tol=1e-7)
    assert math.isclose(m.get_shear_x(), -1.0, abs_tol=1e-7)
    assert math.isclose(m.get_scale_y(), 0.0, abs_tol=1e-7)


# ---------- multiplication ----------


def _filled(matrix: PDMatrix, base: int) -> PDMatrix:
    """Fill a matrix with the pattern (x + y + base) at (x, y)."""
    for x in range(3):
        for y in range(3):
            matrix.set_value(x, y, x + y + base)
    return matrix


def test_multiply_produces_expected_product():
    m1 = _filled(PDMatrix(), 0)
    m2 = _filled(PDMatrix(), 8)
    result = m1.multiply(m2)
    expected = [29, 32, 35, 56, 62, 68, 83, 92, 101]
    assert result.get_single() == [float(v) for v in expected]


def test_multiply_does_not_mutate_operands():
    m1 = _filled(PDMatrix(), 0)
    m2 = _filled(PDMatrix(), 8)
    snap1 = m1.get_single()
    snap2 = m2.get_single()
    m1.multiply(m2)
    assert m1.get_single() == snap1
    assert m2.get_single() == snap2


def test_multiply_self_aliasing_is_safe():
    m = _filled(PDMatrix(), 0)
    result = m.multiply(m)
    expected = [5, 8, 11, 8, 14, 20, 11, 20, 29]
    assert result.get_single() == [float(v) for v in expected]
    # Operand is unchanged
    assert m.get_single() == [0.0, 1.0, 2.0, 1.0, 2.0, 3.0, 2.0, 3.0, 4.0]


def test_concatenate_premultiplies_in_place():
    m1 = _filled(PDMatrix(), 0)
    m2 = _filled(PDMatrix(), 8)
    snap2 = m2.get_single()
    m1.concatenate(m2)
    expected = [29, 56, 83, 32, 62, 92, 35, 68, 101]
    assert m1.get_single() == [float(v) for v in expected]
    # m2 unchanged
    assert m2.get_single() == snap2


def test_concatenate_matrices_static_form_matches_b_multiply_a():
    m1 = _filled(PDMatrix(), 0)
    m2 = _filled(PDMatrix(), 8)
    result = PDMatrix.concatenate_matrices(m1, m2)
    expected = [29, 56, 83, 32, 62, 92, 35, 68, 101]
    assert result.get_single() == [float(v) for v in expected]


# ---------- non-finite guards ----------


def test_multiply_with_double_overflow_raises():
    m = PDMatrix()
    # Python uses 64-bit floats; pick a magnitude whose square overflows
    # to inf (1e200^2 = 1e400 > DBL_MAX ~ 1.8e308).
    m.set_value(0, 0, 1e200)
    with pytest.raises(ValueError):
        m.multiply(m)


def test_multiply_with_nan_raises():
    m = PDMatrix()
    m.set_value(0, 0, float("nan"))
    with pytest.raises(ValueError):
        m.multiply(m)


def test_multiply_with_positive_infinity_raises():
    m = PDMatrix()
    m.set_value(0, 0, float("inf"))
    with pytest.raises(ValueError):
        m.multiply(m)


def test_multiply_with_negative_infinity_raises():
    m = PDMatrix()
    m.set_value(0, 0, float("-inf"))
    with pytest.raises(ValueError):
        m.multiply(m)


# ---------- point transforms ----------


def test_transform_point_through_identity_is_unchanged():
    m = PDMatrix()
    assert m.transform_point(3.0, 4.0) == (3.0, 4.0)


def test_transform_point_through_translation():
    m = PDMatrix.get_translate_instance(10.0, 20.0)
    assert m.transform_point(3.0, 4.0) == (13.0, 24.0)


def test_transform_point_through_scale():
    m = PDMatrix.get_scale_instance(2.0, 3.0)
    assert m.transform_point(5.0, 7.0) == (10.0, 21.0)


# ---------- COS round trip ----------


def test_to_cos_array_emits_six_float_entries():
    m = PDMatrix(2, 4, 5, 8, 2, 0)
    arr = m.to_cos_array()
    assert arr.size() == 6
    assert arr.get(0) == COSFloat(2.0)
    assert arr.get(1) == COSFloat(4.0)
    assert arr.get(2) == COSFloat(5.0)
    assert arr.get(3) == COSFloat(8.0)
    assert arr.get(4) == COSFloat(2.0)
    assert arr.get(5) == COSFloat.ZERO


def test_to_cos_array_round_trip_through_create_matrix():
    src = PDMatrix(1.5, 2.5, 3.5, 4.5, 5.5, 6.5)
    arr = src.to_cos_array()
    rebuilt = PDMatrix.create_matrix(arr)
    assert rebuilt == src


# ---------- predicates ----------


def test_is_identity_true_for_default():
    assert PDMatrix().is_identity()


def test_is_identity_false_after_translation():
    m = PDMatrix()
    m.translate(1, 0)
    assert not m.is_identity()


def test_is_identity_false_for_six_arg_constructor():
    assert not PDMatrix(2, 0, 0, 2, 0, 0).is_identity()


# ---------- copy semantics ----------


def test_clone_produces_independent_copy():
    m1 = PDMatrix()
    m2 = m1.clone()
    assert m1 is not m2
    assert m1 == m2
    m2.translate(1, 2)
    assert m1 != m2


def test_copy_module_clone_produces_independent_copy():
    m1 = PDMatrix(1, 2, 3, 4, 5, 6)
    m2 = copy.copy(m1)
    assert m1 == m2
    assert m1 is not m2
    m2.set_value(0, 0, 99.0)
    assert m1.get_value(0, 0) == 1.0


def test_deepcopy_produces_independent_copy():
    m1 = PDMatrix(1, 2, 3, 4, 5, 6)
    m2 = copy.deepcopy(m1)
    assert m1 == m2
    assert m1 is not m2
    m2.set_value(0, 0, 99.0)
    assert m1.get_value(0, 0) == 1.0


# ---------- equality / hashing ----------


def test_equal_matrices_compare_equal():
    assert PDMatrix() == PDMatrix()
    assert PDMatrix(1, 2, 3, 4, 5, 6) == PDMatrix(1, 2, 3, 4, 5, 6)


def test_unequal_matrices_compare_unequal():
    assert PDMatrix() != PDMatrix(2, 0, 0, 2, 0, 0)


def test_eq_with_non_matrix_returns_not_implemented():
    m = PDMatrix()
    assert m.__eq__(object()) is NotImplemented


def test_hash_consistent_with_equality():
    a = PDMatrix(1, 2, 3, 4, 5, 6)
    b = PDMatrix(1, 2, 3, 4, 5, 6)
    assert hash(a) == hash(b)


def test_hashable_in_set():
    a = PDMatrix(1, 2, 3, 4, 5, 6)
    b = PDMatrix(1, 2, 3, 4, 5, 6)
    s = {a, b}
    assert len(s) == 1


# ---------- __str__ / __repr__ ----------


def test_str_emits_six_numbers_in_order():
    m = PDMatrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    text = str(m)
    assert text.startswith("[")
    assert text.endswith("]")
    parts = text[1:-1].split(",")
    assert parts == ["1.0", "2.0", "3.0", "4.0", "5.0", "6.0"]


def test_repr_includes_six_components():
    m = PDMatrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    text = repr(m)
    assert "PDMatrix" in text
    for component in ("a=1.0", "b=2.0", "c=3.0", "d=4.0", "e=5.0", "f=6.0"):
        assert component in text


# ---------- module surface ----------


def test_pd_matrix_size_constant():
    assert PDMatrix.SIZE == 9


def test_pd_matrix_exported_from_common():
    from pypdfbox.pdmodel.common import PDMatrix as Imported
    assert Imported is PDMatrix
