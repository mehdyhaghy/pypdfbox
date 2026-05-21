"""Wave 1369 — PDFunctionType0 ``/Order`` (linear vs cubic) parity.

The sampled-function spec (PDF 32000-1 §7.10.2) defines two valid
interpolation orders:

* ``/Order = 1`` — n-linear blend of the 2^n surrounding samples (default).
* ``/Order = 3`` — Catmull-Rom cubic Hermite over 4 surrounding samples
  per axis (clamped at the table edges).

Coverage already lives in ``test_pd_function.py`` and
``test_pd_function_type0_eval.py`` for the basic linear vs cubic
discrimination, but this file rounds out:

* The shape contract — cubic and linear agree exactly at every grid index.
* Cubic monotonicity isn't required, but cubic and linear must agree to
  within the cubic-overshoot envelope of [min, max] of the surrounding
  samples after ``/Range`` clipping.
* /Order fallback semantics — any value other than 1 or 3 must fall back
  to linear with no error (logged-warning behaviour, but eval still works).
* /Order interaction with /Decode — the cubic-overshoot clamp happens
  after the decode-map, so a cubic overshoot outside [0, sample_max]
  still maps to a /Range-clipped result.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType0


def _pack_samples(values: list[int], bits: int) -> bytes:
    total_bits = len(values) * bits
    big = 0
    for v in values:
        big = (big << bits) | (v & ((1 << bits) - 1))
    pad = (-total_bits) % 8
    big <<= pad
    nbytes = (total_bits + pad) // 8
    return big.to_bytes(nbytes, "big") if nbytes else b""


def _build(
    *,
    domain: list[float],
    range_: list[float],
    size: list[int],
    bits: int,
    samples: list[int],
    order: int,
    decode: list[float] | None = None,
    encode: list[float] | None = None,
) -> PDFunctionType0:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    domain_arr = COSArray()
    domain_arr.set_float_array(domain)
    raw.set_item("Domain", domain_arr)
    range_arr = COSArray()
    range_arr.set_float_array(range_)
    raw.set_item("Range", range_arr)
    size_arr = COSArray()
    for s in size:
        size_arr.add(COSFloat(float(s)))
    raw.set_item("Size", size_arr)
    raw.set_int("BitsPerSample", bits)
    raw.set_int("Order", order)
    if decode is not None:
        dec = COSArray()
        dec.set_float_array(decode)
        raw.set_item("Decode", dec)
    if encode is not None:
        enc = COSArray()
        enc.set_float_array(encode)
        raw.set_item("Encode", enc)
    raw.set_data(_pack_samples(samples, bits))
    return PDFunctionType0(raw)


# ---------- /Order discriminator: 1 vs 3 produce same value at grid points ----------


@pytest.mark.parametrize("order", [1, 3], ids=["order-1-linear", "order-3-cubic"])
def test_order_agrees_at_grid_points(order: int) -> None:
    """Linear and cubic agree exactly at every grid index — interpolation
    only matters strictly between samples."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[5],
        bits=8,
        samples=[0, 64, 128, 192, 255],
        order=order,
    )
    # 5-cell grid: x maps to encoded coord i = x * 4. Grid indices at
    # x in {0, 0.25, 0.5, 0.75, 1.0} land exactly on samples [0..4].
    for i, x in enumerate([0.0, 0.25, 0.5, 0.75, 1.0]):
        out = fn.eval([x])[0]
        assert math.isclose(
            out, float([0, 64, 128, 192, 255][i]), rel_tol=1e-9, abs_tol=1e-9
        ), f"order={order} x={x} got {out}"


def test_cubic_differs_from_linear_at_non_grid_point() -> None:
    """Cubic interpolation on a curved sample sequence must produce a
    different value than linear at a between-grid point.

    Sample sequence ``[0, 100, 50, 200, 150]`` has enough curvature that
    the Catmull-Rom blend at a quarter-cell offset will not equal the
    pure linear midpoint.
    """
    samples = [0, 100, 50, 200, 150]
    lin = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[5],
        bits=8,
        samples=samples,
        order=1,
    )
    cub = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[5],
        bits=8,
        samples=samples,
        order=3,
    )
    # Pick a point that doesn't fall on a sample index — encoded coord
    # 1.5 = x = 0.375.
    a = lin.eval([0.375])[0]
    b = cub.eval([0.375])[0]
    assert not math.isclose(a, b, rel_tol=1e-3, abs_tol=1e-3), (
        f"cubic ({b}) must differ from linear ({a}) at non-grid point"
    )


# ---------- Catmull-Rom Hermite numeric parity ----------


def test_cubic_midpoint_matches_hand_computed_hermite() -> None:
    """The cubic interpolant at the midpoint between samples 1 and 2 of
    ``[0, 64, 128, 192]`` is computable by hand via the Catmull-Rom
    Hermite basis:

    * ``t = 0.5``
    * ``m1 = (s2 - s0) / 2 = (128 - 0) / 2 = 64``
    * ``m2 = (s3 - s1) / 2 = (192 - 64) / 2 = 64``
    * basis: h00=0.5, h10=0.125, h01=0.5, h11=-0.125
    * result = 0.5 * 64 + 0.125 * 64 + 0.5 * 128 + (-0.125) * 64 = 96
    """
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[4],
        bits=8,
        samples=[0, 64, 128, 192],
        order=3,
    )
    # 4-cell grid: encoded coord 1.5 = x = 0.5.
    out = fn.eval([0.5])[0]
    assert math.isclose(out, 96.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Order fallback ----------


@pytest.mark.parametrize(
    "order",
    [0, 2, 4, 5, -1, 100],
    ids=[f"fallback-order-{o}" for o in [0, 2, 4, 5, -1, 100]],
)
def test_unsupported_order_falls_back_to_linear(order: int) -> None:
    """Any /Order other than {1, 3} must fall back to linear blending —
    eval still works, the result equals the /Order=1 result."""
    samples = [0, 100, 50, 200, 150]
    fb = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[5],
        bits=8,
        samples=samples,
        order=order,
    )
    linear = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[5],
        bits=8,
        samples=samples,
        order=1,
    )
    for x in [0.0, 0.1, 0.35, 0.5, 0.65, 0.9, 1.0]:
        a = fb.eval([x])[0]
        b = linear.eval([x])[0]
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), (
            f"fallback /Order={order} at x={x} got {a} but linear is {b}"
        )


# ---------- Cubic overshoot is /Range-clipped ----------


def test_cubic_overshoot_is_clipped_to_range() -> None:
    """Catmull-Rom can overshoot the surrounding sample envelope; the
    /Range clipping step must catch any over/undershoot so the final
    output stays inside the declared output domain."""
    # A sample pattern (0, 255, 0) creates a sharp peak; the cubic
    # interpolant near sample 1 may overshoot the [0, 255] envelope.
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[3],
        bits=8,
        samples=[0, 255, 0],
        order=3,
    )
    # Sweep across the curve — every value must be within /Range.
    for k in range(0, 101):
        x = k / 100.0
        out = fn.eval([x])[0]
        assert 0.0 <= out <= 255.0, f"x={x} produced out-of-range {out}"


# ---------- /Order = 3 with 2D table ----------


def test_cubic_2d_smoke_at_corners() -> None:
    """For a 4x4 2D table with /Order=3, the corner inputs still hit the
    expected corner samples — the edge-clamped neighbour lookup makes
    boundary cells behave as if the neighbour-1 cell were the same as
    the corner cell."""
    # Plane increasing diagonally with integer codes.
    samples = [
        0, 16, 32, 48,
        64, 80, 96, 112,
        128, 144, 160, 176,
        192, 208, 224, 240,
    ]
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0],
        size=[4, 4],
        bits=8,
        samples=samples,
        order=3,
    )
    # Four corners
    assert math.isclose(fn.eval([0.0, 0.0])[0], 0.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([1.0, 0.0])[0], 48.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([0.0, 1.0])[0], 192.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([1.0, 1.0])[0], 240.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Order with /Decode mapping ----------


def test_cubic_result_is_decoded_then_clipped() -> None:
    """Order=3 evaluates the cubic over raw sample codes; the per-output
    /Decode then maps the (possibly overshooting) sample to a Range pair
    and finally /Range clips the result. Build a table where the cubic
    result is well inside the surrounding-sample envelope so we can
    predict the decoded value exactly.

    Samples ``[10, 20, 30, 40]`` are linear; cubic on linear data is
    exact linear (Catmull-Rom reproduces lines). So eval at the cell
    midpoint between 1 and 2 must equal 25 in sample space, then map
    through /Decode = [0, 100] to ``25 / sample_max * 100`` with
    ``sample_max=255`` → ``9.803921...``.
    """
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 100.0],
        size=[4],
        bits=8,
        samples=[10, 20, 30, 40],
        decode=[0.0, 100.0],
        order=3,
    )
    # Encoded coord 1.5 = x = 0.5
    out = fn.eval([0.5])[0]
    expected = 25.0 / 255.0 * 100.0
    assert math.isclose(out, expected, rel_tol=1e-9, abs_tol=1e-9)
