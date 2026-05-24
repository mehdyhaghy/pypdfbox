"""Wave 1390 — close the final DEFERRED ``PDMatrix`` surface.

Covers the newly-added ``transform`` polymorphic dispatch,
``transform_vector`` (direction-only — translation ignored), and
``create_affine_transform`` (6-tuple in ``java.awt.geom.AffineTransform``
order). These mirror upstream ``PDMatrix.transform(Point2D)`` /
``PDMatrix.transform(Vector)`` / ``PDMatrix.createAffineTransform``
(canonical equivalent at ``pypdfbox.util.matrix.Matrix``).
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.pdmodel.common import PDMatrix
from pypdfbox.util.matrix import Matrix
from pypdfbox.util.vector import Vector

# ---------- transform_point ----------


def test_transform_point_identity_returns_same_coordinates():
    m = PDMatrix()
    out = m.transform_point(3.5, -7.25)
    assert math.isclose(out[0], 3.5)
    assert math.isclose(out[1], -7.25)


def test_transform_point_translate_then_scale_then_rotate():
    # PDFBox/PDMatrix ``multiply(other)`` semantic: apply self first,
    # then other. So ``t.multiply(s).multiply(r)`` applied to point
    # (1, 0) means: translate (10, 20) -> (11, 20); then scale (2, 3)
    # -> (22, 60); then rotate 90deg -> (-60, 22).
    theta = math.pi / 2
    t = PDMatrix.get_translate_instance(10.0, 20.0)
    s = PDMatrix.get_scale_instance(2.0, 3.0)
    r = PDMatrix.get_rotate_instance(theta, 0.0, 0.0)

    composed = t.multiply(s).multiply(r)
    out_x, out_y = composed.transform_point(1.0, 0.0)

    assert math.isclose(out_x, -60.0, abs_tol=1e-9)
    assert math.isclose(out_y, 22.0, abs_tol=1e-9)


# ---------- transform_vector (translation ignored) ----------


def test_transform_vector_ignores_translation():
    # Pure translate -> direction vector unchanged.
    m = PDMatrix.get_translate_instance(50.0, -25.0)
    out = m.transform_vector(Vector(1.0, 0.0))
    assert isinstance(out, Vector)
    assert math.isclose(out.get_x(), 1.0)
    assert math.isclose(out.get_y(), 0.0)


def test_transform_vector_applies_scale():
    m = PDMatrix.get_scale_instance(4.0, 5.0)
    out = m.transform_vector(Vector(2.0, 3.0))
    assert math.isclose(out.get_x(), 8.0)
    assert math.isclose(out.get_y(), 15.0)


def test_transform_vector_applies_rotation():
    m = PDMatrix.get_rotate_instance(math.pi, 0.0, 0.0)
    out = m.transform_vector(Vector(1.0, 0.0))
    assert math.isclose(out.get_x(), -1.0, abs_tol=1e-9)
    assert math.isclose(out.get_y(), 0.0, abs_tol=1e-9)


def test_transform_vector_combined_translation_and_scale_drops_translation():
    # a=2 d=3 (scale), e=100 f=200 (translation): vector should pick up
    # the scale but NOT the translation.
    m = PDMatrix(2.0, 0.0, 0.0, 3.0, 100.0, 200.0)
    out = m.transform_vector(Vector(1.0, 1.0))
    assert math.isclose(out.get_x(), 2.0)
    assert math.isclose(out.get_y(), 3.0)


def test_transform_vector_accepts_tuple_returns_tuple():
    m = PDMatrix.get_scale_instance(2.0, 5.0)
    out = m.transform_vector((3.0, 4.0))
    assert isinstance(out, tuple)
    assert math.isclose(out[0], 6.0)
    assert math.isclose(out[1], 20.0)


# ---------- transform (polymorphic) ----------


def test_transform_with_vector_returns_vector():
    m = PDMatrix.get_scale_instance(2.0, 3.0)
    out = m.transform(Vector(4.0, 5.0))
    assert isinstance(out, Vector)
    assert math.isclose(out.get_x(), 8.0)
    assert math.isclose(out.get_y(), 15.0)


def test_transform_with_tuple_returns_transformed_tuple():
    m = PDMatrix.get_translate_instance(7.0, 9.0)
    out = m.transform((1.0, 2.0))
    assert isinstance(out, tuple)
    assert math.isclose(out[0], 8.0)
    assert math.isclose(out[1], 11.0)


def test_transform_with_point2d_object_mutates_in_place_and_returns_none():
    class _Pt:
        def __init__(self, x: float, y: float) -> None:
            self.x = x
            self.y = y

        def get_x(self) -> float:
            return self.x

        def get_y(self) -> float:
            return self.y

        def set_location(self, x: float, y: float) -> None:
            self.x = x
            self.y = y

    m = PDMatrix.get_scale_instance(2.0, 2.0)
    p = _Pt(3.0, 4.0)
    rv = m.transform(p)
    assert rv is None
    assert math.isclose(p.x, 6.0)
    assert math.isclose(p.y, 8.0)


# ---------- create_affine_transform ----------


def test_create_affine_transform_identity_returns_six_tuple():
    m = PDMatrix()
    aff = m.create_affine_transform()
    assert isinstance(aff, tuple)
    assert len(aff) == 6
    assert aff == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def test_create_affine_transform_six_arg_constructor_round_trip():
    m = PDMatrix(2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
    aff = m.create_affine_transform()
    assert aff == (2.0, 3.0, 4.0, 5.0, 6.0, 7.0)


def test_create_affine_transform_matches_canonical_matrix():
    pd_m = PDMatrix(2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
    util_m = Matrix(2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
    assert pd_m.create_affine_transform() == util_m.create_affine_transform()


@pytest.mark.parametrize(
    ("a", "b", "c", "d", "e", "f"),
    [
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0, 3.0, 0.0, 0.0),
        (math.cos(0.5), math.sin(0.5), -math.sin(0.5), math.cos(0.5), 11.0, 13.0),
    ],
    ids=["identity", "pure_scale", "rotate_plus_translate"],
)
def test_create_affine_transform_matches_constructor_inputs(a, b, c, d, e, f):
    m = PDMatrix(a, b, c, d, e, f)
    aff = m.create_affine_transform()
    assert math.isclose(aff[0], a)
    assert math.isclose(aff[1], b)
    assert math.isclose(aff[2], c)
    assert math.isclose(aff[3], d)
    assert math.isclose(aff[4], e)
    assert math.isclose(aff[5], f)
