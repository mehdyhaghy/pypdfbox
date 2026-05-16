"""Coverage-boost tests for ``pypdfbox.util.matrix``.

Targets uncovered paths in ``Matrix``:
- single-arg constructor: list of 9 floats (private) + bad single arg
- 1/3/4/5/7-arg constructors raise
- ``create_matrix`` rejection paths (non-COSArray, too small, non-numeric)
- ``set_value`` / ``get_values`` matrix shape
- ``concatenate`` (in-place) + non-finite guard
- ``translate(x, y)`` AND ``translate(Vector)`` overloads
- ``scale`` (all 6 cells touched)
- ``rotate`` matches a fresh ``get_rotate_instance`` matrix
- ``transform`` with Vector, tuple, and Point2D-like object (``set_location``)
- scaling-factor accessors when shear is non-zero AND zero
- ``concatenate_matrices`` static
- ``clone`` produces independent storage
- equality / hashing / repr / ``equals`` / ``hash_code`` / ``to_string``
- ``create_affine_transform`` returns the 6-tuple
- ``check_float_values`` / ``multiply_arrays`` static parity surface
- ``check_float_values`` raises on NaN
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_name import COSName
from pypdfbox.util.matrix import SIZE, Matrix
from pypdfbox.util.vector import Vector


# ---- constructor edge cases ----


def test_constructor_with_9_float_list_uses_storage_directly() -> None:
    storage = [1.0, 2.0, 0.0, 3.0, 4.0, 0.0, 5.0, 6.0, 1.0]
    m = Matrix(storage)
    # private ctor must NOT clone.
    assert m._single is storage


def test_constructor_with_bad_single_arg_raises() -> None:
    with pytest.raises(TypeError, match="6 floats"):
        Matrix("nope")


def test_constructor_with_wrong_arg_count_raises() -> None:
    with pytest.raises(TypeError, match="Unsupported Matrix constructor"):
        Matrix(1.0, 2.0, 3.0)


# ---- create_matrix rejection branches ----


def test_create_matrix_with_non_cosarray_returns_identity() -> None:
    m = Matrix.create_matrix(COSName.get_pdf_name("Foo"))
    assert m == Matrix()


def test_create_matrix_with_none_returns_identity() -> None:
    assert Matrix.create_matrix(None) == Matrix()


def test_create_matrix_with_short_array_returns_identity() -> None:
    arr = COSArray()
    for _ in range(5):
        arr.add(COSFloat(1.0))
    assert Matrix.create_matrix(arr) == Matrix()


def test_create_matrix_with_nonnumeric_entry_returns_identity() -> None:
    arr = COSArray()
    for _ in range(5):
        arr.add(COSFloat(1.0))
    arr.add(COSName.get_pdf_name("Bad"))  # 6th entry is non-numeric
    assert Matrix.create_matrix(arr) == Matrix()


def test_create_matrix_with_valid_six_floats_round_trips() -> None:
    arr = COSArray()
    for v in (2.0, 0.0, 0.0, 3.0, 4.0, 5.0):
        arr.add(COSFloat(v))
    m = Matrix.create_matrix(arr)
    assert m.get_scale_x() == 2.0
    assert m.get_scale_y() == 3.0
    assert m.get_translate_x() == 4.0
    assert m.get_translate_y() == 5.0


# ---- accessors / mutators ----


def test_set_value_mutates_underlying_storage() -> None:
    m = Matrix()
    m.set_value(0, 0, 9.5)
    assert m.get_value(0, 0) == 9.5


def test_get_values_returns_3x3_shape() -> None:
    m = Matrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    rows = m.get_values()
    assert len(rows) == 3
    assert all(len(r) == 3 for r in rows)
    assert rows[0][0] == 1.0
    assert rows[2][0] == 5.0


def test_size_class_constant_matches_module_size() -> None:
    assert Matrix.SIZE == SIZE == 9


# ---- arithmetic ----


def test_concatenate_in_place_left_multiplies() -> None:
    translate = Matrix.get_translate_instance(2.0, 3.0)
    a = Matrix()
    a.concatenate(translate)
    # Identity concatenated with a translate => the translate.
    assert a.get_translate_x() == 2.0
    assert a.get_translate_y() == 3.0


def test_translate_two_arg_form() -> None:
    m = Matrix()
    m.translate(4.0, 5.0)
    assert m.get_translate_x() == 4.0
    assert m.get_translate_y() == 5.0


def test_translate_vector_overload() -> None:
    m = Matrix()
    m.translate(Vector(7.0, 8.0))
    assert m.get_translate_x() == 7.0
    assert m.get_translate_y() == 8.0


def test_scale_mutates_first_two_rows() -> None:
    m = Matrix(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    m.scale(2.0, 3.0)
    assert m.get_scale_x() == 2.0
    assert m.get_scale_y() == 3.0
    # Translate row untouched.
    assert m.get_translate_x() == 0.0


def test_rotate_matches_get_rotate_instance() -> None:
    m = Matrix()
    m.rotate(math.pi / 2)
    expected = Matrix.get_rotate_instance(math.pi / 2, 0.0, 0.0)
    # m == identity * R = R
    assert math.isclose(m.get_value(0, 0), expected.get_value(0, 0), abs_tol=1e-12)
    assert math.isclose(m.get_value(0, 1), expected.get_value(0, 1), abs_tol=1e-12)


def test_multiply_does_not_mutate_either_operand() -> None:
    a = Matrix.get_translate_instance(1.0, 2.0)
    b = Matrix.get_scale_instance(2.0, 2.0)
    out = a.multiply(b)
    assert a.get_translate_x() == 1.0
    assert b.get_scale_x() == 2.0
    # The product applies B then A (column vectors): translate*scale.
    assert out is not a
    assert out is not b


# ---- transform overloads ----


def test_transform_with_vector_returns_new_vector() -> None:
    m = Matrix.get_translate_instance(10.0, 20.0)
    out = m.transform(Vector(1.0, 2.0))
    assert isinstance(out, Vector)
    assert out.get_x() == 11.0
    assert out.get_y() == 22.0


def test_transform_with_tuple_returns_point_tuple() -> None:
    m = Matrix.get_translate_instance(10.0, 20.0)
    out = m.transform((1.0, 2.0))
    assert out == (11.0, 22.0)


def test_transform_with_point2d_like_mutates_via_set_location() -> None:
    class _Point:
        def __init__(self, x: float, y: float) -> None:
            self._x, self._y = x, y

        def get_x(self) -> float:
            return self._x

        def get_y(self) -> float:
            return self._y

        def set_location(self, nx: float, ny: float) -> None:
            self._x, self._y = nx, ny

    p = _Point(1.0, 2.0)
    m = Matrix.get_translate_instance(5.0, 7.0)
    assert m.transform(p) is None
    assert (p._x, p._y) == (6.0, 9.0)


# ---- scaling/shear accessors ----


def test_scaling_factor_x_with_zero_shear() -> None:
    m = Matrix(3.0, 0.0, 0.0, 4.0, 0.0, 0.0)
    assert m.get_scaling_factor_x() == 3.0


def test_scaling_factor_x_with_nonzero_shear() -> None:
    m = Matrix(3.0, 4.0, 0.0, 1.0, 0.0, 0.0)
    # sqrt(3^2 + 4^2) == 5
    assert m.get_scaling_factor_x() == 5.0


def test_scaling_factor_y_with_zero_shear() -> None:
    m = Matrix(1.0, 0.0, 0.0, 7.0, 0.0, 0.0)
    assert m.get_scaling_factor_y() == 7.0


def test_scaling_factor_y_with_nonzero_shear() -> None:
    m = Matrix(1.0, 0.0, 3.0, 4.0, 0.0, 0.0)
    assert m.get_scaling_factor_y() == 5.0


def test_shear_accessors_return_off_diagonal_entries() -> None:
    m = Matrix(1.0, 0.5, 0.25, 1.0, 0.0, 0.0)
    assert m.get_shear_y() == 0.5
    assert m.get_shear_x() == 0.25


# ---- static helpers ----


def test_concatenate_matrices_static_is_right_then_left() -> None:
    a = Matrix.get_translate_instance(1.0, 2.0)
    b = Matrix.get_scale_instance(3.0, 4.0)
    # Matrix.concatenate(a, b) returns b.multiply(a)
    expected = b.multiply(a)
    assert Matrix.concatenate_matrices(a, b) == expected


def test_clone_produces_independent_storage() -> None:
    m = Matrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    c = m.clone()
    assert c == m
    c.set_value(0, 0, 99.0)
    assert m.get_value(0, 0) == 1.0


def test_check_float_values_static_passes_finite_list() -> None:
    vals = [0.0] * SIZE
    assert Matrix.check_float_values(vals) is vals


def test_check_float_values_static_raises_on_nan() -> None:
    bad = [float("nan")] * SIZE
    with pytest.raises(ValueError, match="illegal values"):
        Matrix.check_float_values(bad)


def test_multiply_arrays_static_matches_instance_multiply() -> None:
    a = Matrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    b = Matrix(7.0, 8.0, 9.0, 10.0, 11.0, 12.0)
    raw = Matrix.multiply_arrays(a._single, b._single)
    assert raw == a.multiply(b)._single


# ---- equality / hashing / repr ----


def test_equality_with_self_short_circuits_true() -> None:
    m = Matrix()
    assert m == m  # noqa: PLR0124 - exercising __eq__ self-shortcut


def test_equality_with_non_matrix_returns_false() -> None:
    assert (Matrix() == "not a matrix") is False


def test_hash_and_hash_code_match() -> None:
    m = Matrix(1.0, 0.0, 0.0, 1.0, 3.0, 4.0)
    assert m.hash_code() == hash(m)


def test_equals_parity_method_matches_dunder() -> None:
    a = Matrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    b = Matrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    c = Matrix()
    assert a.equals(b)
    assert not a.equals(c)


def test_repr_and_to_string_match() -> None:
    m = Matrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    assert m.to_string() == repr(m)
    assert "1.0" in repr(m)


def test_create_affine_transform_returns_6_tuple() -> None:
    m = Matrix(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    assert m.create_affine_transform() == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
