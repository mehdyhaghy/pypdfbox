"""Wave 1369 — PDFunctionType0 multi-dimensional /Size + /Encode + /Decode.

The existing eval test suite covers 1D and 2D tables but doesn't reach
3D, 4D, or asymmetric /Size shapes where each axis has a different sample
count. This file rounds out:

* 3-input / 3-output (RGB-out from a 3D LUT, the common CMYK→RGB shape).
* Asymmetric /Size where each axis has a different sample count, so the
  linear-stride math in ``_read_sample`` is exercised against a non-
  square table.
* /Encode reversal — encoding a single dimension in reverse maps grid
  index 0 to the high end of /Domain.
* /Decode mapping to negative ranges (e.g. ``[-1, 1]`` for Lab-style
  signed outputs).
* Default /Decode falls back to the /Range array (per PDF 32000-1
  Table 38) when /Decode is absent.
* Default /Encode falls back to ``(0, Size[i] - 1)`` per axis when
  /Encode is absent.
* Out-of-domain inputs clip first, then encode/lookup proceeds.
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
    encode: list[float] | None = None,
    decode: list[float] | None = None,
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
    if encode is not None:
        enc = COSArray()
        enc.set_float_array(encode)
        raw.set_item("Encode", enc)
    if decode is not None:
        dec = COSArray()
        dec.set_float_array(decode)
        raw.set_item("Decode", dec)
    raw.set_data(_pack_samples(samples, bits))
    return PDFunctionType0(raw)


# ---------- Asymmetric /Size ----------


def test_asymmetric_size_2x3_at_corners() -> None:
    """A 2x3 grid (2 cells along axis 0, 3 along axis 1) places samples
    at linear index = x + 2 * y. Corners reach their packed samples
    directly."""
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0],
        size=[2, 3],
        bits=8,
        # row 0: (0,0)=10  (1,0)=20
        # row 1: (0,1)=30  (1,1)=40
        # row 2: (0,2)=50  (1,2)=60
        samples=[10, 20, 30, 40, 50, 60],
    )
    assert math.isclose(fn.eval([0.0, 0.0])[0], 10.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([1.0, 0.0])[0], 20.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([0.0, 1.0])[0], 50.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([1.0, 1.0])[0], 60.0, rel_tol=1e-9, abs_tol=1e-9)
    # Middle row, x=0 -> (0, 1) -> sample 30
    assert math.isclose(fn.eval([0.0, 0.5])[0], 30.0, rel_tol=1e-9, abs_tol=1e-9)


def test_asymmetric_size_2x3x4_indexing() -> None:
    """3D table with /Size = [2, 3, 4]: total = 24 cells.

    Linear index = x + 2*y + 6*z. Corner samples reach the packed sample
    code directly.
    """
    # Build samples where each value encodes its (x, y, z) coord
    # uniquely: sample[i] = i * 10 (clamped under sample_max=255).
    size = [2, 3, 4]
    total = size[0] * size[1] * size[2]
    samples = [i * 10 for i in range(total)]
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0],
        size=size,
        bits=8,
        samples=samples,
    )
    # x=0,y=0,z=0 -> linear 0 -> 0
    assert math.isclose(fn.eval([0.0, 0.0, 0.0])[0], 0.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=1,y=0,z=0 -> linear 1 -> 10
    assert math.isclose(fn.eval([1.0, 0.0, 0.0])[0], 10.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=0,y=1,z=0 -> linear 2 -> 20
    assert math.isclose(fn.eval([0.0, 0.5, 0.0])[0], 20.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=0,y=0,z=1 -> linear 6 -> 60
    assert math.isclose(
        fn.eval([0.0, 0.0, 1.0 / 3.0])[0], 60.0, rel_tol=1e-9, abs_tol=1e-9
    )
    # x=1,y=2,z=3 -> linear 23 -> 230
    assert math.isclose(fn.eval([1.0, 1.0, 1.0])[0], 230.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- 3-input, 3-output (CMYK-ish to RGB) ----------


def test_3in_3out_each_output_independent() -> None:
    """Each output channel reads its own per-cell sample at the same
    coordinate; the channels are independent (no cross-channel blending
    introduced by /Order=1)."""
    # 2x2x2 grid -> 8 cells, 3 channels = 24 samples.
    # Each corner stores (R, G, B) = (axis0_high * 255, axis1_high * 255,
    # axis2_high * 255). So corner at (1, 1, 1) is (255, 255, 255).
    samples: list[int] = []
    for z in range(2):
        for y in range(2):
            for x in range(2):
                samples.extend([x * 255, y * 255, z * 255])
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        size=[2, 2, 2],
        bits=8,
        samples=samples,
    )
    assert fn.eval([0.0, 0.0, 0.0]) == pytest.approx([0.0, 0.0, 0.0], abs=1e-9)
    assert fn.eval([1.0, 0.0, 0.0]) == pytest.approx([1.0, 0.0, 0.0], abs=1e-9)
    assert fn.eval([0.0, 1.0, 0.0]) == pytest.approx([0.0, 1.0, 0.0], abs=1e-9)
    assert fn.eval([0.0, 0.0, 1.0]) == pytest.approx([0.0, 0.0, 1.0], abs=1e-9)
    assert fn.eval([1.0, 1.0, 1.0]) == pytest.approx([1.0, 1.0, 1.0], abs=1e-9)
    # Centre is the trilinear average of all 8 corners per channel — by
    # symmetry each channel averages to 0.5.
    centre = fn.eval([0.5, 0.5, 0.5])
    assert centre == pytest.approx([0.5, 0.5, 0.5], abs=1e-9)


# ---------- /Encode reversal ----------


def test_encode_reverses_first_dimension() -> None:
    """An /Encode pair ``(Size-1, 0)`` reverses the encoded coordinate
    so x=0 in /Domain hits the *right* end of the sample grid."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[4],
        bits=8,
        samples=[10, 20, 30, 40],
        encode=[3.0, 0.0],  # reversed
    )
    # x=0 -> encoded coord = 3 -> sample[3] = 40
    assert math.isclose(fn.eval([0.0])[0], 40.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=1 -> encoded coord = 0 -> sample[0] = 10
    assert math.isclose(fn.eval([1.0])[0], 10.0, rel_tol=1e-9, abs_tol=1e-9)


def test_encode_default_uses_size_minus_one_per_axis() -> None:
    """Without /Encode, each input dim defaults to ``(0, Size[i] - 1)``.

    Confirm the default by setting /Encode explicitly to the default
    value and showing the eval result is identical."""
    samples = [10, 20, 30, 40, 50, 60, 70, 80]
    fn_default = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0],
        size=[4, 2],
        bits=8,
        samples=samples,
    )
    fn_explicit = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0],
        size=[4, 2],
        bits=8,
        samples=samples,
        encode=[0.0, 3.0, 0.0, 1.0],  # spec default
    )
    for x in [0.0, 0.25, 0.5, 0.75, 1.0]:
        for y in [0.0, 0.5, 1.0]:
            a = fn_default.eval([x, y])[0]
            b = fn_explicit.eval([x, y])[0]
            assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), (
                f"default vs explicit /Encode mismatch at ({x}, {y}): {a} != {b}"
            )


# ---------- /Decode mapping ----------


def test_decode_maps_to_negative_range() -> None:
    """/Decode = [-1, 1] maps sample 0 -> -1, sample_max -> 1, mid -> 0."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[-1.0, 1.0],
        size=[3],
        bits=8,
        samples=[0, 127, 255],
        decode=[-1.0, 1.0],
    )
    assert math.isclose(fn.eval([0.0])[0], -1.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([1.0])[0], 1.0, rel_tol=1e-9, abs_tol=1e-9)
    # Mid sample 127 -> 127/255*2 - 1 ~= -0.0039
    expected = 127.0 / 255.0 * 2.0 - 1.0
    assert math.isclose(fn.eval([0.5])[0], expected, rel_tol=1e-9, abs_tol=1e-9)


def test_decode_default_uses_range_pair() -> None:
    """Absent /Decode -> /Range is used as the decode pair per axis."""
    samples = [0, 64, 128, 255]
    fn_default = _build(
        domain=[0.0, 1.0],
        range_=[-10.0, 10.0],
        size=[4],
        bits=8,
        samples=samples,
    )
    fn_explicit = _build(
        domain=[0.0, 1.0],
        range_=[-10.0, 10.0],
        size=[4],
        bits=8,
        samples=samples,
        decode=[-10.0, 10.0],
    )
    for x in [0.0, 0.25, 0.5, 0.75, 1.0]:
        a = fn_default.eval([x])[0]
        b = fn_explicit.eval([x])[0]
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def test_decode_inverted_mapping_inverts_output() -> None:
    """/Decode = [1, 0] inverts the sample mapping: 0 -> 1, max -> 0."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        samples=[0, 127, 255],
        decode=[1.0, 0.0],
    )
    assert math.isclose(fn.eval([0.0])[0], 1.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([1.0])[0], 0.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Domain clipping ----------


def test_input_clipped_to_domain_before_encode() -> None:
    """Out-of-domain inputs clip first; an input below /Domain[0] is
    treated as /Domain[0] when looking up samples."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[3],
        bits=8,
        samples=[10, 20, 30],
    )
    # x=-5 clips to 0 -> sample 0 -> 10
    assert math.isclose(fn.eval([-5.0])[0], 10.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=10 clips to 1 -> sample 2 -> 30
    assert math.isclose(fn.eval([10.0])[0], 30.0, rel_tol=1e-9, abs_tol=1e-9)


def test_input_clipped_per_axis_independently() -> None:
    """Each axis clips against its own /Domain pair; over-the-top in one
    dim doesn't affect the other dim's clipping."""
    fn = _build(
        domain=[0.0, 1.0, -2.0, 2.0],
        range_=[0.0, 255.0],
        size=[2, 2],
        bits=8,
        samples=[10, 20, 30, 40],
    )
    # x=2 clips to 1, y=-5 clips to -2 -> (1, 0) -> sample 1 -> 20
    assert math.isclose(fn.eval([2.0, -5.0])[0], 20.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=-1 clips to 0, y=10 clips to 2 -> (0, 1) -> sample 2 -> 30
    assert math.isclose(fn.eval([-1.0, 10.0])[0], 30.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Encode clamps encoded coord to [0, Size-1] ----------


def test_encode_overshoot_clamps_to_grid_edge() -> None:
    """If /Encode maps the input above Size-1, the encoded coord is
    clamped to the grid edge (per §7.10.2 step e' = min(max(...)))."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[3],
        bits=8,
        samples=[10, 20, 30],
        # /Encode = [-5, 10] over-extends beyond [0, Size-1] = [0, 2].
        encode=[-5.0, 10.0],
    )
    # x=0 -> encoded -5 -> clamped to 0 -> sample 10
    assert math.isclose(fn.eval([0.0])[0], 10.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=1 -> encoded 10 -> clamped to 2 -> sample 30
    assert math.isclose(fn.eval([1.0])[0], 30.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Range clips decoded output ----------


def test_range_clips_decoded_output() -> None:
    """When /Decode maps outside /Range, the final output is clipped."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 100.0],
        size=[2],
        bits=8,
        samples=[0, 255],
        # /Decode = [0, 500] would produce 500 at sample 255, but /Range
        # caps that to 100.
        decode=[0.0, 500.0],
    )
    assert math.isclose(fn.eval([1.0])[0], 100.0, rel_tol=1e-9, abs_tol=1e-9)
