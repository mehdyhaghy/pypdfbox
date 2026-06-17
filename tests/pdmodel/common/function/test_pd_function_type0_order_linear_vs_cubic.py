"""PDFunctionType0 ``/Order`` parity — upstream always interpolates linearly.

Originally (wave 1369) this file pinned a Catmull-Rom cubic spline for
``/Order = 3``. Wave 1500's parity audit (round 7) verified against the live
PDFBox 3.0.7 jar that upstream ``PDFunctionType0.eval`` has **no cubic
branch**: it reads neither honours ``/Order`` — every input is interpolated
n-linearly regardless. pypdfbox was reverted to match (parity is the metric,
the project's "Behavior over style" rule), so this file now pins the corrected
contract: ``/Order = 1`` and ``/Order = 3`` (and every other value) produce
byte-identical linear output.
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


# ---------- /Order is ignored: 1 and 3 agree everywhere ----------


@pytest.mark.parametrize("order", [1, 3], ids=["order-1", "order-3"])
def test_order_agrees_at_grid_points(order: int) -> None:
    """Linear and "cubic" agree exactly at every grid index."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[5],
        bits=8,
        samples=[0, 64, 128, 192, 255],
        order=order,
    )
    for i, x in enumerate([0.0, 0.25, 0.5, 0.75, 1.0]):
        out = fn.eval([x])[0]
        assert math.isclose(
            out, float([0, 64, 128, 192, 255][i]), rel_tol=1e-9, abs_tol=1e-9
        ), f"order={order} x={x} got {out}"


def test_order3_equals_order1_at_non_grid_point() -> None:
    """Upstream ignores /Order, so /Order = 3 produces the SAME linear value
    as /Order = 1 at a between-grid point — there is no cubic divergence.

    (Verified against the PDFBox 3.0.7 jar: a sample sequence with curvature
    yields identical output for /Order 1 and 3.)
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
    a = lin.eval([0.375])[0]
    b = cub.eval([0.375])[0]
    assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), (
        f"/Order=3 ({b}) must equal /Order=1 ({a}) — upstream ignores /Order"
    )


# ---------- every /Order value behaves linearly ----------


@pytest.mark.parametrize(
    "order",
    [0, 2, 3, 4, 5, -1, 100],
    ids=[f"order-{o}" for o in [0, 2, 3, 4, 5, -1, 100]],
)
def test_any_order_behaves_linearly(order: int) -> None:
    """Any /Order value (including 3) interpolates linearly — the result
    equals the /Order = 1 result at every probed input."""
    samples = [0, 100, 50, 200, 150]
    other = _build(
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
        a = other.eval([x])[0]
        b = linear.eval([x])[0]
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), (
            f"/Order={order} at x={x} got {a} but linear is {b}"
        )


def test_order3_on_linear_data_is_exact_linear() -> None:
    """Linear sample data interpolates linearly under any /Order. The cell
    midpoint between samples 1 and 2 of ``[0, 64, 128, 192]`` is the linear
    average 96 — the same value linear interpolation gives."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[4],
        bits=8,
        samples=[0, 64, 128, 192],
        order=3,
    )
    out = fn.eval([0.5])[0]
    assert math.isclose(out, 96.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Range clipping still applies ----------


def test_output_is_range_clipped() -> None:
    """Every interpolated output stays inside the declared /Range."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[3],
        bits=8,
        samples=[0, 255, 0],
        order=3,
    )
    for k in range(0, 101):
        x = k / 100.0
        out = fn.eval([x])[0]
        assert 0.0 <= out <= 255.0, f"x={x} produced out-of-range {out}"


# ---------- 2D /Order = 3 corners ----------


def test_order3_2d_smoke_at_corners() -> None:
    """For a 4x4 2D table the corner inputs hit the expected corner samples
    under /Order = 3 (linear interpolation, edge-clamped)."""
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
    assert math.isclose(fn.eval([0.0, 0.0])[0], 0.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([1.0, 0.0])[0], 48.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([0.0, 1.0])[0], 192.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([1.0, 1.0])[0], 240.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Decode mapping ----------


def test_result_is_decoded_then_clipped() -> None:
    """Linear sample data decoded through /Decode = [0, 100]: the midpoint of
    samples 1 and 2 of ``[10, 20, 30, 40]`` is 25 in sample space, mapped to
    ``25 / 255 * 100``."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 100.0],
        size=[4],
        bits=8,
        samples=[10, 20, 30, 40],
        decode=[0.0, 100.0],
        order=3,
    )
    out = fn.eval([0.5])[0]
    expected = 25.0 / 255.0 * 100.0
    assert math.isclose(out, expected, rel_tol=1e-9, abs_tol=1e-9)
