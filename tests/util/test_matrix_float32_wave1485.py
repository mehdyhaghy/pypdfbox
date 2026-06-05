"""Float32-narrowing parity for ``pypdfbox.util.Matrix`` / ``Vector``.

Upstream ``org.apache.pdfbox.util.Matrix`` stores its nine cells in a Java
``float[]`` (32-bit), and ``Vector`` stores two ``float`` fields. Every value
written to the matrix — and every intermediate in the float-typed arithmetic of
``multiplyArrays`` / ``transformPoint`` / ``translate`` / ``scale`` and the
``cos``/``sin`` of ``getRotateInstance`` — is single precision. pypdfbox keeps
Python ``float`` (64-bit) objects but rounds each store/operation to the nearest
float32 so the observable element values match Apache PDFBox bit-for-bit.

The expected values below were pinned from the live ``MatrixFloat32Probe``
oracle (Apache PDFBox 3.0.7), rendered via ``Float.toString`` (the shortest
round-tripping float32 decimal). Each pinned test passes WITHOUT the oracle; the
``@requires_oracle`` differential at the bottom re-derives them live.

Before wave 1485 ``Matrix`` stored float64, so e.g.
``getRotateInstance(0.1).toString()`` produced
``[0.9950041652780258,0.09983341664682815,...]`` — a divergence on every
non-trivial rotate, multiply chain, sheared scaling factor, and transformed
point.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos.cos_float import format_float32
from pypdfbox.util.matrix import Matrix, f32
from pypdfbox.util.vector import Vector


def _cells(m: Matrix) -> tuple[str, str, str, str, str, str]:
    """The six geometric cells rendered as Java ``Float.toString`` would."""
    s = m._single
    return tuple(format_float32(s[i]) for i in (0, 1, 3, 4, 6, 7))  # type: ignore[return-value]


# --- getRotateInstance: cos/sin narrowed to float32 ---------------------


def test_rotate_0p1_radians_matches_float32_cells() -> None:
    m = Matrix.get_rotate_instance(0.1, 0.0, 0.0)
    assert _cells(m) == (
        "0.9950042",
        "0.099833414",
        "-0.099833414",
        "0.9950042",
        "0.0",
        "0.0",
    )


def test_rotate_30_degrees_with_translation() -> None:
    m = Matrix.get_rotate_instance(math.radians(30), 5.0, 7.0)
    assert _cells(m) == ("0.8660254", "0.5", "-0.5", "0.8660254", "5.0", "7.0")


def test_rotate_2p5_radians_negative_cells() -> None:
    m = Matrix.get_rotate_instance(2.5, -3.0, 4.0)
    assert _cells(m) == (
        "-0.8011436",
        "0.5984721",
        "-0.5984721",
        "-0.8011436",
        "-3.0",
        "4.0",
    )


def test_rotate_tostring_renders_float32_not_float64() -> None:
    # Pre-fix this rendered the float64 repr 0.9950041652780258.
    assert (
        repr(Matrix.get_rotate_instance(0.1, 0.0, 0.0))
        == "[0.9950042,0.099833414,-0.099833414,0.9950042,0.0,0.0]"
    )


# --- concatenate chain: float32 accumulation ----------------------------


def test_ten_rotate_translate_concatenations_accumulate_in_float32() -> None:
    chain = Matrix()
    for _ in range(10):
        chain.concatenate(Matrix.get_rotate_instance(0.1, 1.0, 2.0))
    assert _cells(chain) == (
        "0.54030246",
        "0.841471",
        "-0.841471",
        "0.54030246",
        "0.29272634",
        "21.4475",
    )


# --- multiply order: this-times-other -----------------------------------


def test_multiply_is_this_times_other() -> None:
    a = Matrix.get_rotate_instance(0.3, 0.0, 0.0)
    b = Matrix.get_scale_instance(2.5, 1.3)
    assert _cells(a.multiply(b)) == (
        "2.3883412",
        "0.38417625",
        "-0.7388005",
        "1.2419374",
        "0.0",
        "0.0",
    )
    # The reversed product differs (non-commutative) — guards the order.
    assert _cells(b.multiply(a)) == (
        "2.3883412",
        "0.7388005",
        "-0.38417625",
        "1.2419374",
        "0.0",
        "0.0",
    )


def test_concatenate_matrices_static_is_b_multiply_a() -> None:
    a = Matrix.get_rotate_instance(0.3, 0.0, 0.0)
    b = Matrix.get_scale_instance(2.5, 1.3)
    # Matrix.concatenate(a, b) == b.multiply(a) — matches b_mul_a above.
    assert _cells(Matrix.concatenate_matrices(a, b)) == _cells(b.multiply(a))


# --- getScalingFactorX/Y: PDFBOX-4148 sqrt, narrowed to float32 ---------


def test_scaling_factor_on_sheared_matrix_is_float32_sqrt() -> None:
    shear = Matrix(2.0, 4.0, 4.0, 2.0, 0.0, 0.0)
    assert format_float32(shear.get_scaling_factor_x()) == "4.472136"
    assert format_float32(shear.get_scaling_factor_y()) == "4.472136"


def test_scaling_factor_on_fractional_shear() -> None:
    m = Matrix(0.7, 0.13, 0.31, 0.9, 0.0, 0.0)
    assert format_float32(m.get_scaling_factor_x()) == "0.7119691"
    assert format_float32(m.get_scaling_factor_y()) == "0.95189285"


def test_scaling_factor_zero_shear_returns_raw_element() -> None:
    m = Matrix(0.1, 0.0, 0.0, 0.7, 0.0, 0.0)
    # The zero-shear branch returns the raw (already float32) element.
    assert format_float32(m.get_scaling_factor_x()) == "0.1"
    assert format_float32(m.get_scaling_factor_y()) == "0.7"


def test_scaling_factor_x_treats_negative_zero_shear_as_nonzero() -> None:
    # Float.compare(-0.0f, 0.0f) != 0 in Java, so a -0.0 shear takes the sqrt
    # branch — sqrt(scaleX^2 + 0) == |scaleX|.
    m = Matrix(2.0, 4.0, 4.0, 2.0, 0.0, 0.0)
    m.set_value(0, 1, -0.0)  # hy = -0.0
    assert m.get_scaling_factor_x() == 2.0


# --- transformPoint / transform(Vector): float32 arithmetic -------------


def test_transform_point_is_float32() -> None:
    m = Matrix.get_rotate_instance(0.1, 3.0, 4.0)
    x, y = m.transform_point(1.234, 5.678)
    assert format_float32(x) == "3.6609812"
    assert format_float32(y) == "9.772828"


def test_transform_vector_matches_transform_point() -> None:
    m = Matrix.get_rotate_instance(0.1, 3.0, 4.0)
    v = m.transform(Vector(1.234, 5.678))
    assert isinstance(v, Vector)
    assert format_float32(v.get_x()) == "3.6609812"
    assert format_float32(v.get_y()) == "9.772828"


# --- createAffineTransform: raw float32 cells widened to double ----------


def test_create_affine_transform_returns_float32_widened_cells() -> None:
    cells = Matrix.get_rotate_instance(0.1, 0.0, 0.0).create_affine_transform()
    # The cell is the float32 0.9950042f, whose exact double value is this.
    assert cells[0] == 0.9950041770935059
    assert cells[1] == 0.0998334139585495


# --- Vector: float32 narrowing on construction + scale ------------------


def test_vector_narrows_components_on_construction() -> None:
    v = Vector(0.1, 1.0 / 3.0)
    assert v.get_x() == f32(0.1)
    assert format_float32(v.get_y()) == "0.33333334"


def test_vector_scale_is_float32() -> None:
    vs = Vector(0.1, 0.2).scale(0.3)
    assert format_float32(vs.get_x()) == "0.030000001"
    assert format_float32(vs.get_y()) == "0.060000002"


def test_vector_tostring_renders_float32() -> None:
    assert Vector(0.1, 0.2).to_string() == "(0.1, 0.2)"


# --- toCOSArray emits float32 cells -------------------------------------


def test_to_cos_array_carries_float32_cells() -> None:
    from pypdfbox.cos.cos_number import COSNumber

    m = Matrix.get_rotate_instance(0.1, 1.5, 2.5)
    arr = m.to_cos_array()
    rendered = [format_float32(arr.get_object(i).float_value()) for i in range(6)]
    assert rendered == [
        "0.9950042",
        "0.099833414",
        "-0.099833414",
        "0.9950042",
        "1.5",
        "2.5",
    ]
    assert all(isinstance(arr.get_object(i), COSNumber) for i in range(6))


# --- live differential ---------------------------------------------------

try:
    from tests.oracle.harness import requires_oracle, run_probe_text
except Exception:  # pragma: no cover - harness optional
    requires_oracle = pytest.mark.skip(reason="oracle harness unavailable")

    def run_probe_text(*_a: str, **_k: object) -> str:  # type: ignore[misc]
        return ""


@requires_oracle
def test_matrix_float32_matches_live_oracle() -> None:
    """Re-derive every pinned value from the live PDFBox ``MatrixFloat32Probe``
    and confirm pypdfbox reproduces each line byte-for-byte."""
    lines = run_probe_text("MatrixFloat32Probe").splitlines()
    oracle = dict(line.split("=", 1) for line in lines if "=" in line)

    def m_cells(label: str, mtx: Matrix) -> None:
        s = mtx._single
        for nm, idx in (("sx", 0), ("hy", 1), ("hx", 3), ("sy", 4), ("tx", 6), ("ty", 7)):
            assert format_float32(s[idx]) == oracle[f"{label}.{nm}"], f"{label}.{nm}"

    m_cells("rot_0p1", Matrix.get_rotate_instance(0.1, 0.0, 0.0))
    m_cells("rot_30deg", Matrix.get_rotate_instance(math.radians(30), 5.0, 7.0))
    m_cells("rot_1rad", Matrix.get_rotate_instance(1.0, 0.0, 0.0))
    m_cells("rot_2p5", Matrix.get_rotate_instance(2.5, -3.0, 4.0))

    chain = Matrix()
    for _ in range(10):
        chain.concatenate(Matrix.get_rotate_instance(0.1, 1.0, 2.0))
    m_cells("chain10", chain)

    a = Matrix.get_rotate_instance(0.3, 0.0, 0.0)
    b = Matrix.get_scale_instance(2.5, 1.3)
    m_cells("a_mul_b", a.multiply(b))
    m_cells("b_mul_a", b.multiply(a))
    m_cells("concat_ab", Matrix.concatenate_matrices(a, b))

    shear = Matrix(2.0, 4.0, 4.0, 2.0, 0.0, 0.0)
    assert format_float32(shear.get_scaling_factor_x()) == oracle["shear.sfx"]
    assert format_float32(shear.get_scaling_factor_y()) == oracle["shear.sfy"]
    shear2 = Matrix(0.7, 0.13, 0.31, 0.9, 0.0, 0.0)
    assert format_float32(shear2.get_scaling_factor_x()) == oracle["shear2.sfx"]
    assert format_float32(shear2.get_scaling_factor_y()) == oracle["shear2.sfy"]

    tp = Matrix.get_rotate_instance(0.1, 3.0, 4.0)
    x, y = tp.transform_point(1.234, 5.678)
    assert format_float32(x) == oracle["tp.x"]
    assert format_float32(y) == oracle["tp.y"]

    vs = Vector(0.1, 0.2).scale(0.3)
    assert format_float32(vs.get_x()) == oracle["vec_scaled.x"]
    assert format_float32(vs.get_y()) == oracle["vec_scaled.y"]
