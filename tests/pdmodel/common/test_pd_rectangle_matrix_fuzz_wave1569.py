"""Fuzz/parity hammer for PDRectangle + Matrix transform math (wave 1569).

Pins behavioural parity with Apache PDFBox 3.0.7 across the crossing edges of
``org.apache.pdfbox.pdmodel.common.PDRectangle`` and
``org.apache.pdfbox.util.Matrix``:

* PDRectangle normalization (reversed corners → min/max), COSArray round-trip,
  ``getWidth`` / ``getHeight`` (subtract two float cells), ``contains`` edge
  inclusivity, ``transform(Matrix)`` corner projection.
* **float32 storage parity (real fix this wave).** Upstream stores each corner
  in a ``COSArray`` of ``COSFloat`` and reads it back through
  ``COSNumber.floatValue()`` — i.e. every coordinate is IEEE-754 single
  precision, and ``getWidth = getUpperRightX() - getLowerLeftX()`` is a float
  subtraction returning a float. pypdfbox previously stored corners as Python
  float64; for non-float-representable coordinates that diverged from PDFBox
  (e.g. ``getWidth`` of ``[100000.1, 100000.7]`` was ``0.5999999999912689``
  instead of upstream's ``0.6015625``). Fixed wave 1569 — corners are now
  narrowed on store and the width/height subtraction is narrowed too.
* Matrix multiply / concatenate order (upstream: ``concatenate`` does
  ``multiplyArrays(matrix.single, single)`` = ``other * this``; ``multiply``
  does ``multiplyArrays(this, other)``), translate / scale / rotate factories,
  ``getScalingFactorX/Y`` (``sqrt(a^2+b^2)`` via ``Float.compare`` against the
  shear cell), ``getTranslateX/Y``, ``transformPoint``, the 3x3 / 6-value
  ``(a b c d e f)`` representation, identity, ``createAffineTransform``.

Every expected value below is derived by hand from the upstream Java semantics
(no live oracle dependency); the matrix-only differential against the PDFBox
3.0.7 jar lives in ``tests/util/oracle/test_matrix_ops_fuzz_wave1532.py`` and
``tests/pdmodel/common/oracle/test_rect_matrix_fuzz_wave1561.py``.
"""

from __future__ import annotations

import math
import struct

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.util.matrix import Matrix, f32


def _f32(value: float) -> float:
    return struct.unpack(">f", struct.pack(">f", value))[0]


# --------------------------------------------------------------------------
# PDRectangle: construction, accessors, width/height
# --------------------------------------------------------------------------


def test_basic_accessors():
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert r.get_lower_left_x() == 10.0
    assert r.get_lower_left_y() == 20.0
    assert r.get_upper_right_x() == 110.0
    assert r.get_upper_right_y() == 220.0
    assert r.get_width() == 100.0
    assert r.get_height() == 200.0


def test_from_width_height_origin_zero():
    r = PDRectangle.from_width_height(300.0, 400.0)
    assert (r.get_lower_left_x(), r.get_lower_left_y()) == (0.0, 0.0)
    assert (r.get_upper_right_x(), r.get_upper_right_y()) == (300.0, 400.0)
    assert (r.get_width(), r.get_height()) == (300.0, 400.0)


def test_from_xywh_corner_sums():
    r = PDRectangle.from_xywh(50.0, 60.0, 100.0, 200.0)
    assert r.get_upper_right_x() == 150.0
    assert r.get_upper_right_y() == 260.0
    assert (r.get_width(), r.get_height()) == (100.0, 200.0)


def test_width_height_float32_subtraction():
    # Upstream getWidth = float(urx) - float(llx), all single precision.
    # 100000.1 and 100000.7 are NOT exactly float32-representable.
    r = PDRectangle(100000.1, 0.0, 100000.7, 0.0)
    assert r.get_lower_left_x() == _f32(100000.1)
    assert r.get_upper_right_x() == _f32(100000.7)
    expected_w = _f32(_f32(100000.7) - _f32(100000.1))
    assert r.get_width() == expected_w
    assert r.get_width() == 0.6015625
    # The naive float64 subtraction would give 0.5999999999912689 — assert we
    # are NOT that (regression guard for the wave-1569 fix).
    assert r.get_width() != (100000.7 - 100000.1)


def test_corner_storage_narrows_to_float32():
    r = PDRectangle(0.1, 0.2, 0.3, 0.7)
    for got, raw in (
        (r.get_lower_left_x(), 0.1),
        (r.get_lower_left_y(), 0.2),
        (r.get_upper_right_x(), 0.3),
        (r.get_upper_right_y(), 0.7),
    ):
        assert got == _f32(raw)


def test_setters_narrow_to_float32():
    r = PDRectangle()
    r.set_lower_left_x(0.1)
    r.set_lower_left_y(0.2)
    r.set_upper_right_x(0.3)
    r.set_upper_right_y(0.7)
    assert r.get_lower_left_x() == _f32(0.1)
    assert r.get_upper_right_y() == _f32(0.7)
    assert r.get_width() == _f32(_f32(0.3) - _f32(0.1))


# --------------------------------------------------------------------------
# PDRectangle: COSArray construction / normalization / round-trip
# --------------------------------------------------------------------------


def test_from_cos_array_normalizes_reversed_corners():
    # Reversed: upper-right given before lower-left. Upstream uses min/max so
    # width/height come out non-negative (PDF spec 7.9.5).
    arr = COSArray([COSFloat(110.0), COSFloat(220.0), COSFloat(10.0), COSFloat(20.0)])
    r = PDRectangle.from_cos_array(arr)
    assert r.get_lower_left_x() == 10.0
    assert r.get_lower_left_y() == 20.0
    assert r.get_upper_right_x() == 110.0
    assert r.get_upper_right_y() == 220.0
    assert r.get_width() == 100.0
    assert r.get_height() == 200.0


def test_from_cos_array_partially_reversed():
    # x reversed, y in order.
    arr = COSArray([COSFloat(110.0), COSFloat(20.0), COSFloat(10.0), COSFloat(220.0)])
    r = PDRectangle.from_cos_array(arr)
    assert r.get_lower_left_x() == 10.0
    assert r.get_upper_right_x() == 110.0
    assert r.get_lower_left_y() == 20.0
    assert r.get_upper_right_y() == 220.0


def test_from_cos_array_short_zero_padded():
    arr = COSArray([COSFloat(5.0), COSFloat(6.0)])
    r = PDRectangle.from_cos_array(arr)
    # missing entries → 0.0, then min/max.
    assert r.get_lower_left_x() == 0.0
    assert r.get_lower_left_y() == 0.0
    assert r.get_upper_right_x() == 5.0
    assert r.get_upper_right_y() == 6.0


def test_from_cos_array_empty():
    r = PDRectangle.from_cos_array(COSArray())
    assert (r.get_width(), r.get_height()) == (0.0, 0.0)


def test_from_cos_array_too_long_truncated():
    arr = COSArray(
        [COSFloat(1.0), COSFloat(2.0), COSFloat(3.0), COSFloat(4.0), COSFloat(99.0)]
    )
    r = PDRectangle.from_cos_array(arr)
    assert r.get_upper_right_x() == 3.0
    assert r.get_upper_right_y() == 4.0


def test_from_cos_array_non_numeric_becomes_zero():
    arr = COSArray([COSName.A, COSFloat(50.0), COSFloat(10.0), COSFloat(60.0)])
    r = PDRectangle.from_cos_array(arr)
    # entry 0 (name) → 0.0; min(0, 10)=0 llx, max(0,10)=10 urx.
    assert r.get_lower_left_x() == 0.0
    assert r.get_upper_right_x() == 10.0


def test_from_cos_array_integer_entries():
    arr = COSArray([COSInteger.get(0), COSInteger.get(0), COSInteger.get(612), COSInteger.get(792)])
    r = PDRectangle.from_cos_array(arr)
    assert (r.get_width(), r.get_height()) == (612.0, 792.0)


def test_from_cos_array_clamps_huge_magnitude():
    # PDFBOX-2818: |value| > (float)Integer.MAX_VALUE clamps to +/-2147483648.0.
    big = 5_000_000_000.0
    arr = COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(big), COSFloat(-big)])
    r = PDRectangle.from_cos_array(arr)
    assert r.get_upper_right_x() == 2147483648.0
    assert r.get_lower_left_y() == -2147483648.0


def test_to_cos_array_round_trip():
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    arr = r.to_cos_array()
    assert arr.size() == 4
    assert arr.get(0) == COSFloat(10.0)
    assert arr.get(1) == COSFloat(20.0)
    assert arr.get(2) == COSFloat(110.0)
    assert arr.get(3) == COSFloat(220.0)
    back = PDRectangle.from_cos_array(arr)
    assert back == r


def test_get_cos_array_aliases():
    r = PDRectangle(1.0, 2.0, 3.0, 4.0)
    assert r.get_cos_array().size() == 4
    assert r.get_cos_object().size() == 4


def test_to_string_no_spaces():
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert r.to_string() == "[10.0,20.0,110.0,220.0]"


# --------------------------------------------------------------------------
# PDRectangle: contains() edge inclusivity
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (60.0, 70.0, True),  # interior
        (10.0, 20.0, True),  # lower-left corner (inclusive)
        (110.0, 220.0, True),  # upper-right corner (inclusive)
        (10.0, 120.0, True),  # left edge
        (110.0, 120.0, True),  # right edge
        (60.0, 20.0, True),  # bottom edge
        (60.0, 220.0, True),  # top edge
        (9.999, 70.0, False),  # just left
        (110.001, 70.0, False),  # just right
        (60.0, 19.999, False),  # just below
        (60.0, 220.001, False),  # just above
    ],
)
def test_contains_edges(x, y, expected):
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert r.contains(x, y) is expected


def test_create_retranslated_rectangle():
    r = PDRectangle(100.0, 100.0, 400.0, 400.0)
    rt = r.create_retranslated_rectangle()
    assert (rt.get_lower_left_x(), rt.get_lower_left_y()) == (0.0, 0.0)
    assert (rt.get_upper_right_x(), rt.get_upper_right_y()) == (300.0, 300.0)


def test_to_general_path_corner_order():
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert r.to_general_path() == [
        (10.0, 20.0),
        (110.0, 20.0),
        (110.0, 220.0),
        (10.0, 220.0),
    ]


# --------------------------------------------------------------------------
# PDRectangle.transform(Matrix)
# --------------------------------------------------------------------------


def test_transform_identity_returns_corners():
    r = PDRectangle(10.0, 20.0, 110.0, 220.0)
    assert r.transform(Matrix()) == [
        (10.0, 20.0),
        (110.0, 20.0),
        (110.0, 220.0),
        (10.0, 220.0),
    ]


def test_transform_translate():
    r = PDRectangle(0.0, 0.0, 100.0, 200.0)
    m = Matrix.get_translate_instance(10.0, 20.0)
    assert r.transform(m) == [
        (10.0, 20.0),
        (110.0, 20.0),
        (110.0, 220.0),
        (10.0, 220.0),
    ]


def test_transform_scale():
    r = PDRectangle(1.0, 1.0, 3.0, 5.0)
    m = Matrix.get_scale_instance(2.0, 3.0)
    assert r.transform(m) == [
        (2.0, 3.0),
        (6.0, 3.0),
        (6.0, 15.0),
        (2.0, 15.0),
    ]


def test_transform_90_rotation():
    r = PDRectangle(0.0, 0.0, 100.0, 200.0)
    m = Matrix.get_rotate_instance(math.pi / 2.0, 0.0, 0.0)
    pts = r.transform(m)
    # 90 rotation: (x,y) -> (-y, x). cos(pi/2) is a tiny float32 epsilon.
    eps = f32(math.cos(math.pi / 2.0))
    assert pts[0] == pytest.approx((0.0, 0.0), abs=1e-9)
    assert pts[1] == pytest.approx((eps * 100.0, 100.0), abs=1e-9)
    assert pts[2] == pytest.approx((eps * 100.0 - 200.0, 100.0 + eps * 200.0), abs=1e-9)
    assert pts[3] == pytest.approx((-200.0, eps * 200.0), abs=1e-9)


# --------------------------------------------------------------------------
# Matrix: factories, accessors, 6-value representation
# --------------------------------------------------------------------------


def test_identity_matrix():
    m = Matrix()
    assert m.get_values() == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def test_six_value_layout():
    m = Matrix(2.0, 4.0, 5.0, 8.0, 3.0, 7.0)
    # a b 0 / c d 0 / e f 1
    assert m.get_value(0, 0) == 2.0  # a
    assert m.get_value(0, 1) == 4.0  # b
    assert m.get_value(0, 2) == 0.0
    assert m.get_value(1, 0) == 5.0  # c
    assert m.get_value(1, 1) == 8.0  # d
    assert m.get_value(1, 2) == 0.0
    assert m.get_value(2, 0) == 3.0  # e
    assert m.get_value(2, 1) == 7.0  # f
    assert m.get_value(2, 2) == 1.0


def test_create_affine_transform_order():
    m = Matrix(2.0, 4.0, 5.0, 8.0, 3.0, 7.0)
    assert m.create_affine_transform() == (2.0, 4.0, 5.0, 8.0, 3.0, 7.0)


def test_translate_factory_values():
    m = Matrix.get_translate_instance(15.0, 30.0)
    assert m.get_translate_x() == 15.0
    assert m.get_translate_y() == 30.0
    assert m.get_value(0, 0) == 1.0
    assert m.get_value(1, 1) == 1.0


def test_scale_factory_values():
    m = Matrix.get_scale_instance(2.0, 3.0)
    assert m.get_scale_x() == 2.0
    assert m.get_scale_y() == 3.0
    assert m.get_translate_x() == 0.0


def test_rotate_factory_values():
    theta = math.pi / 6.0  # 30 degrees
    m = Matrix.get_rotate_instance(theta, 5.0, 6.0)
    # a b c d e f = cos, sin, -sin, cos, tx, ty
    assert m.get_value(0, 0) == f32(math.cos(theta))
    assert m.get_value(0, 1) == f32(math.sin(theta))
    assert m.get_value(1, 0) == f32(-f32(math.sin(theta)))
    assert m.get_value(1, 1) == f32(math.cos(theta))
    assert m.get_translate_x() == 5.0
    assert m.get_translate_y() == 6.0


def test_rotate_direction_counterclockwise():
    # Positive theta rotates the +x axis toward +y: sin term is +.
    m = Matrix.get_rotate_instance(math.pi / 2.0, 0.0, 0.0)
    assert m.get_value(0, 1) == pytest.approx(1.0, abs=1e-6)  # sin(90) = +1
    assert m.get_value(1, 0) == pytest.approx(-1.0, abs=1e-6)  # -sin(90) = -1


# --------------------------------------------------------------------------
# Matrix: multiply / concatenate order
# --------------------------------------------------------------------------


def test_multiply_is_this_times_other():
    scale = Matrix.get_scale_instance(2.0, 3.0)
    translate = Matrix.get_translate_instance(10.0, 20.0)
    # multiply(self, other) = multiplyArrays(self, other): scale row dominates,
    # translate's e/f pass through unchanged.
    product = scale.multiply(translate)
    assert product.get_value(2, 0) == 10.0
    assert product.get_value(2, 1) == 20.0
    assert product.get_value(0, 0) == 2.0
    assert product.get_value(1, 1) == 3.0


def test_concatenate_is_other_times_this():
    scale = Matrix.get_scale_instance(2.0, 3.0)
    translate = Matrix.get_translate_instance(10.0, 20.0)
    m = scale.clone()
    m.concatenate(translate)  # multiplyArrays(translate, scale): translate*scale
    assert m.get_value(2, 0) == 20.0  # 10 * 2
    assert m.get_value(2, 1) == 60.0  # 20 * 3


def test_multiply_order_matters():
    scale = Matrix.get_scale_instance(2.0, 3.0)
    translate = Matrix.get_translate_instance(10.0, 20.0)
    ab = scale.multiply(translate)
    ba = translate.multiply(scale)
    assert ab.get_value(2, 0) != ba.get_value(2, 0)
    assert ab.get_value(2, 0) == 10.0
    assert ba.get_value(2, 0) == 20.0


def test_concatenate_matrices_static_equals_b_multiply_a():
    a = Matrix.get_scale_instance(2.0, 3.0)
    b = Matrix.get_translate_instance(10.0, 20.0)
    assert Matrix.concatenate_matrices(a, b).get_values() == b.multiply(a).get_values()


def test_multiply_operands_unchanged():
    a = Matrix(2.0, 4.0, 4.0, 2.0, 1.0, 1.0)
    b = Matrix(1.0, 0.0, 0.0, 1.0, 5.0, 6.0)
    before_a = a.get_values()
    before_b = b.get_values()
    a.multiply(b)
    assert a.get_values() == before_a
    assert b.get_values() == before_b


def test_multiply_nonfinite_raises():
    m = Matrix()
    m.set_value(0, 0, math.inf)
    with pytest.raises(ValueError):
        m.multiply(m)


# --------------------------------------------------------------------------
# Matrix: transformPoint / scaling factors / translate / scale mutation
# --------------------------------------------------------------------------


def test_transform_point_translate():
    m = Matrix.get_translate_instance(10.0, 20.0)
    assert m.transform_point(5.0, 7.0) == (15.0, 27.0)


def test_transform_point_scale():
    m = Matrix.get_scale_instance(2.0, 3.0)
    assert m.transform_point(4.0, 5.0) == (8.0, 15.0)


def test_transform_point_full_affine():
    # x*a + y*c + e , x*b + y*d + f
    m = Matrix(2.0, 1.0, 3.0, 4.0, 10.0, 20.0)
    # (1,1): 1*2 + 1*3 + 10 = 15 ; 1*1 + 1*4 + 20 = 25
    assert m.transform_point(1.0, 1.0) == (15.0, 25.0)


def test_scaling_factor_pythagorean():
    # single[1] (shear y) nonzero -> sqrt(a^2 + b^2).
    m = Matrix(2.0, 4.0, 4.0, 2.0, 0.0, 0.0)
    assert m.get_scaling_factor_x() == f32(math.sqrt(2.0**2 + 4.0**2))
    assert m.get_scaling_factor_y() == f32(math.sqrt(4.0**2 + 2.0**2))


def test_scaling_factor_no_shear_returns_scale_cell():
    # single[1] == 0 -> returns single[0]; single[3] == 0 -> returns single[4].
    m = Matrix(3.0, 0.0, 0.0, 5.0, 0.0, 0.0)
    assert m.get_scaling_factor_x() == 3.0
    assert m.get_scaling_factor_y() == 5.0


def test_scaling_factor_negative_zero_shear_counts_as_nonzero():
    # Float.compare(-0.0, 0.0) != 0 -> pythagorean branch even though |b|==0.
    m = Matrix(3.0, -0.0, -0.0, 5.0, 0.0, 0.0)
    assert m.get_scaling_factor_x() == f32(math.sqrt(3.0**2 + 0.0**2))
    assert m.get_scaling_factor_y() == f32(math.sqrt(0.0**2 + 5.0**2))


def test_scaling_factor_identity():
    m = Matrix()
    assert m.get_scaling_factor_x() == 1.0
    assert m.get_scaling_factor_y() == 1.0


def test_translate_mutation():
    m = Matrix(2.0, 4.0, 4.0, 2.0, 15.0, 30.0)
    m.translate(2.0, 3.0)
    # single[6] += tx*a + ty*c ; single[7] += tx*b + ty*d
    assert m.get_value(2, 0) == 15.0 + (2.0 * 2.0 + 3.0 * 4.0)  # 31
    assert m.get_value(2, 1) == 30.0 + (2.0 * 4.0 + 3.0 * 2.0)  # 44


def test_scale_mutation():
    m = Matrix(2.0, 4.0, 4.0, 2.0, 15.0, 30.0)
    m.scale(2.0, 3.0)
    assert m.get_value(0, 0) == 4.0
    assert m.get_value(0, 1) == 8.0
    assert m.get_value(1, 0) == 12.0
    assert m.get_value(1, 1) == 6.0
    # translate row unchanged
    assert m.get_value(2, 0) == 15.0
    assert m.get_value(2, 1) == 30.0


def test_to_cos_array_six_floats():
    m = Matrix(2.0, 4.0, 5.0, 8.0, 2.0, 0.0)
    arr = m.to_cos_array()
    assert arr.size() == 6
    assert arr.get(0) == COSFloat(2.0)
    assert arr.get(5) == COSFloat.ZERO


def test_create_matrix_from_cos_array_round_trip():
    src = Matrix(2.0, 4.0, 5.0, 8.0, 3.0, 7.0)
    rebuilt = Matrix.create_matrix(src.to_cos_array())
    assert rebuilt.get_values() == src.get_values()


def test_create_matrix_invalid_returns_identity():
    assert Matrix.create_matrix(None).get_values() == Matrix().get_values()
    assert Matrix.create_matrix(COSName.A).get_values() == Matrix().get_values()
    short = COSArray([COSFloat(1.0)])
    assert Matrix.create_matrix(short).get_values() == Matrix().get_values()
