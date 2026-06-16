"""Fuzz / exactness coverage for ``PDFunctionType0`` (sampled-table function).

Wave 1573 (Agent B). Hammers the §7.10.2 pipeline:

* MSB-first bit-stream unpacking at every spec width — especially the
  non-byte-aligned 1/2/4/12-bit cases where the bit reader's correctness is
  load-bearing.
* the ``/Encode`` default ``[0 .. Size[i]-1]`` per input dim,
* the ``/Decode`` default ``= /Range``,
* 1-input linear lookup at exact sample hits and interpolated midpoints,
* 2-input bilinear interpolation over a 2D grid,
* clamping of inputs to ``/Domain`` and outputs to ``/Range``,
* the ``interpolate`` helper exactness,
* boundary inputs (domain min/max → first/last sample),
* the ``Size = 1`` degenerate dimension.

Each numeric assertion is checked against an independent reference
implementation of the spec formula (``_ref_eval`` below), not against the
production code, so a divergence in the production interpolation/decoding is
caught rather than mirrored.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType0
from pypdfbox.pdmodel.common.function.pd_function import PDFunction

# ---------- packing helper (MSB-first, no inter-sample padding) ----------


def _pack_samples(values: list[int], bits: int) -> bytes:
    total_bits = len(values) * bits
    big = 0
    for v in values:
        big = (big << bits) | (v & ((1 << bits) - 1))
    pad = (-total_bits) % 8
    big <<= pad
    nbytes = (total_bits + pad) // 8
    return big.to_bytes(nbytes, "big") if nbytes else b""


def _build_type0(
    *,
    domain: list[float],
    range_: list[float],
    size: list[int],
    bits: int,
    samples: list[int],
    encode: list[float] | None = None,
    decode: list[float] | None = None,
    order: int | None = None,
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
    if order is not None:
        raw.set_int("Order", order)

    raw.set_data(_pack_samples(samples, bits))
    return PDFunctionType0(raw)


# ---------- independent spec reference implementation ----------


def _clip(x: float, lo: float, hi: float) -> float:
    """Non-normalising scalar clamp (Java clipToRange(F,F,F))."""
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _ref_eval(
    inputs: list[float],
    *,
    domain: list[float],
    range_: list[float],
    size: list[int],
    bits: int,
    samples: list[int],
    encode: list[float] | None = None,
    decode: list[float] | None = None,
) -> list[float]:
    """Pure-Python §7.10.2 reference. First input dim varies fastest."""
    num_in = len(domain) // 2
    num_out = len(range_) // 2
    if encode is None:
        encode = []
        for i in range(num_in):
            encode += [0.0, float(size[i] - 1)]
    if decode is None:
        decode = list(range_)

    sample_max = (1 << bits) - 1

    def sample_at(coords: list[int], j: int) -> int:
        linear = 0
        stride = 1
        for i in range(num_in):
            linear += coords[i] * stride
            stride *= size[i]
        flat_index = linear * num_out + j
        v = samples[flat_index]
        if bits == 32 and v >= 0x80000000:
            v -= 0x100000000
        return v

    floors: list[int] = []
    fracs: list[float] = []
    for i in range(num_in):
        d_lo, d_hi = domain[2 * i], domain[2 * i + 1]
        e_lo, e_hi = encode[2 * i], encode[2 * i + 1]
        x = _clip(inputs[i], d_lo, d_hi)
        e = e_lo if d_hi == d_lo else (x - d_lo) * (e_hi - e_lo) / (d_hi - d_lo) + e_lo
        upper = size[i] - 1
        e = _clip(e, 0.0, float(upper))
        f = int(e)
        if f >= upper:
            f = upper
            frac = 0.0
        else:
            frac = e - f
        floors.append(f)
        fracs.append(frac)

    out: list[float] = []
    for j in range(num_out):
        corners: list[float] = []
        for idx in range(1 << num_in):
            coords: list[int] = []
            for i in range(num_in):
                pos = (idx >> i) & 1
                raw = min(floors[i] + pos, size[i] - 1)
                coords.append(raw)
            corners.append(float(sample_at(coords, j)))
        for i in range(num_in):
            t = fracs[i]
            corners = [
                corners[k] + t * (corners[k + 1] - corners[k])
                for k in range(0, len(corners), 2)
            ]
        s = corners[0]
        d_lo, d_hi = decode[2 * j], decode[2 * j + 1]
        dec = d_lo if sample_max == 0 else s * (d_hi - d_lo) / sample_max + d_lo
        r_lo, r_hi = range_[2 * j], range_[2 * j + 1]
        out.append(_clip(dec, r_lo, r_hi))
    return out


def _assert_close(a: list[float], b: list[float], tol: float = 1e-6) -> None:
    assert len(a) == len(b), (a, b)
    for x, y in zip(a, b, strict=True):
        assert abs(x - y) <= tol, (a, b)


# ====================================================================
# 1-input → 1-output linear lookup
# ====================================================================


def test_1d_8bit_exact_sample_hits() -> None:
    samples = [0, 64, 128, 255]
    fn = _build_type0(
        domain=[0.0, 1.0], range_=[0.0, 1.0], size=[4], bits=8, samples=samples
    )
    # Encode maps domain [0,1] → grid [0,3]. Exact hits at the four sample x's.
    for k, _ in enumerate(samples):
        x = k / 3.0
        expected = samples[k] / 255.0
        got = fn.eval([x])
        _assert_close(got, [expected])


def test_1d_8bit_interpolated_midpoint() -> None:
    samples = [0, 100, 200, 250]
    fn = _build_type0(
        domain=[0.0, 1.0], range_=[0.0, 1.0], size=[4], bits=8, samples=samples
    )
    # Midpoint between grid 0 and 1: x = 0.5/3.
    x = 0.5 / 3.0
    expected = ((0 + 100) / 2) / 255.0
    _assert_close(fn.eval([x]), [expected])
    # Midpoint between grid 2 and 3.
    x2 = 2.5 / 3.0
    expected2 = ((200 + 250) / 2) / 255.0
    _assert_close(fn.eval([x2]), [expected2])


@pytest.mark.parametrize(
    "x",
    [0.0, 0.1, 0.2, 0.3333, 0.5, 0.6, 0.75, 0.9, 1.0],
    ids=["x0", "x01", "x02", "x033", "x05", "x06", "x075", "x09", "x10"],
)
def test_1d_matches_reference(x: float) -> None:
    samples = [10, 70, 130, 200, 255]
    kw = dict(domain=[0.0, 1.0], range_=[0.0, 1.0], size=[5], bits=8, samples=samples)
    fn = _build_type0(**kw)
    _assert_close(fn.eval([x]), _ref_eval([x], **kw))


# ====================================================================
# /Encode default and explicit
# ====================================================================


def test_encode_default_is_zero_to_size_minus_one() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0], range_=[0.0, 1.0], size=[4], bits=8, samples=[0, 0, 0, 0]
    )
    enc = fn.get_encode_values()
    assert enc is not None
    assert enc.to_float_array() == [0.0, 3.0]


def test_encode_default_multi_dim() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3, 5],
        bits=8,
        samples=[0] * 15,
    )
    enc = fn.get_encode_values()
    assert enc is not None
    assert enc.to_float_array() == [0.0, 2.0, 0.0, 4.0]


def test_explicit_encode_remaps_grid() -> None:
    samples = [0, 50, 100, 150, 200, 250]
    # Encode [5,0] reverses the grid: domain min → sample index 5.
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[6],
        bits=8,
        samples=samples,
        encode=[5.0, 0.0],
    )
    fn = _build_type0(**kw)
    # domain 0 → grid 5 → sample 250.
    _assert_close(fn.eval([0.0]), [250.0 / 255.0])
    # domain 1 → grid 0 → sample 0.
    _assert_close(fn.eval([1.0]), [0.0])
    for x in (0.25, 0.5, 0.75):
        _assert_close(fn.eval([x]), _ref_eval([x], **kw))


# ====================================================================
# /Decode default = /Range, and explicit Decode
# ====================================================================


def test_decode_default_equals_range() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[-1.0, 2.0],
        size=[2],
        bits=8,
        samples=[0, 255],
    )
    dec = fn.get_decode_values()
    assert dec is not None
    assert dec.to_float_array() == [-1.0, 2.0]
    # sample 0 → decode lo (-1), sample 255 → decode hi (2).
    _assert_close(fn.eval([0.0]), [-1.0])
    _assert_close(fn.eval([1.0]), [2.0])


def test_explicit_decode_independent_of_range() -> None:
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 100.0],
        size=[2],
        bits=8,
        samples=[0, 255],
        decode=[10.0, 90.0],
    )
    fn = _build_type0(**kw)
    _assert_close(fn.eval([0.0]), [10.0])
    _assert_close(fn.eval([1.0]), [90.0])
    _assert_close(fn.eval([0.5]), _ref_eval([0.5], **kw))


# ====================================================================
# /BitsPerSample unpacking — non-byte-aligned widths
# ====================================================================


@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16])
def test_bit_unpacking_roundtrip_via_decode(bits: int) -> None:
    """Map each sample code straight through (Decode = [0, 2^bits-1]) and
    verify the unpacked code equals the packed one for every grid point."""
    smax = (1 << bits) - 1
    # A spread of codes across the value space, length = size.
    size = 7
    samples = [int(round(k * smax / (size - 1))) for k in range(size)]
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, float(smax)],
        size=[size],
        bits=bits,
        samples=samples,
        decode=[0.0, float(smax)],
    )
    fn = _build_type0(**kw)
    for k in range(size):
        x = k / (size - 1)
        got = fn.eval([x])
        _assert_close(got, [float(samples[k])])


def test_12bit_specific_codes() -> None:
    # 12-bit straddles byte boundaries: codes [0xFFF, 0x000, 0xAAA, 0x555].
    samples = [0xFFF, 0x000, 0xAAA, 0x555]
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 4095.0],
        size=[4],
        bits=12,
        samples=samples,
        decode=[0.0, 4095.0],
    )
    fn = _build_type0(**kw)
    for k in range(4):
        x = k / 3.0
        _assert_close(fn.eval([x]), [float(samples[k])])


def test_1bit_packing() -> None:
    # 8 one-bit samples in a single byte, alternating.
    samples = [1, 0, 1, 0, 1, 0, 1, 0]
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[8],
        bits=1,
        samples=samples,
        decode=[0.0, 1.0],
    )
    fn = _build_type0(**kw)
    for k in range(8):
        x = k / 7.0
        _assert_close(fn.eval([x]), [float(samples[k])])


def test_4bit_nibbles() -> None:
    samples = [0x0, 0x5, 0xA, 0xF, 0x3, 0xC]
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 15.0],
        size=[6],
        bits=4,
        samples=samples,
        decode=[0.0, 15.0],
    )
    fn = _build_type0(**kw)
    for k in range(6):
        x = k / 5.0
        _assert_close(fn.eval([x]), [float(samples[k])])


@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16, 24])
def test_multi_output_unpacking(bits: int) -> None:
    """Two outputs interleaved per cell — checks the per-output bit offset.

    Widths up to 24 read as plain unsigned codes; 32 is exercised separately
    (its top-bit codes sign-extend per the upstream Java ``(int)`` cast)."""
    smax = (1 << bits) - 1
    # 3 grid points, 2 outputs each: cell0=[a0,b0], cell1=[a1,b1], cell2=[a2,b2]
    out_a = [0, smax // 2, smax]
    out_b = [smax, smax // 3, 0]
    samples = []
    for k in range(3):
        samples += [out_a[k], out_b[k]]
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, float(smax), 0.0, float(smax)],
        size=[3],
        bits=bits,
        samples=samples,
        decode=[0.0, float(smax), 0.0, float(smax)],
    )
    fn = _build_type0(**kw)
    for k in range(3):
        x = k / 2.0
        _assert_close(fn.eval([x]), [float(out_a[k]), float(out_b[k])], tol=1e-3)


# ====================================================================
# 2-input bilinear interpolation
# ====================================================================


def _bilinear_grid_fn(samples: list[int]):
    return _build_type0(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0],
        size=[2, 2],
        bits=8,
        samples=samples,
        decode=[0.0, 255.0],
    )


def test_bilinear_corners() -> None:
    # Grid layout: first input varies fastest.
    # cell index = x0 + x1*2. samples = [c00, c10, c01, c11].
    samples = [0, 255, 100, 200]
    fn = _bilinear_grid_fn(samples)
    _assert_close(fn.eval([0.0, 0.0]), [0.0])
    _assert_close(fn.eval([1.0, 0.0]), [255.0])
    _assert_close(fn.eval([0.0, 1.0]), [100.0])
    _assert_close(fn.eval([1.0, 1.0]), [200.0])


def test_bilinear_center() -> None:
    samples = [0, 255, 100, 200]
    fn = _bilinear_grid_fn(samples)
    # center: average of all four corners.
    expected = (0 + 255 + 100 + 200) / 4.0
    _assert_close(fn.eval([0.5, 0.5]), [expected])


@pytest.mark.parametrize(
    "pt",
    [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.5, 0.0), (0.0, 0.5), (0.9, 0.1)],
    ids=["a", "b", "c", "d", "e", "f"],
)
def test_bilinear_matches_reference(pt) -> None:
    samples = [10, 240, 60, 180]
    kw = dict(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2, 2],
        bits=8,
        samples=samples,
        decode=[0.0, 255.0],
    )
    fn = _build_type0(**kw)
    _assert_close(fn.eval(list(pt)), _ref_eval(list(pt), **kw))


def test_2d_3x2_grid_matches_reference() -> None:
    # 3 x 2 grid, first dim varies fastest. 6 cells, 1 output.
    samples = [0, 50, 100, 150, 200, 250]
    kw = dict(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0],
        size=[3, 2],
        bits=8,
        samples=samples,
        decode=[0.0, 255.0],
    )
    fn = _build_type0(**kw)
    for p in [(0.0, 0.0), (0.5, 0.0), (1.0, 0.0), (0.25, 1.0), (0.5, 0.5)]:
        _assert_close(fn.eval(list(p)), _ref_eval(list(p), **kw))


# ====================================================================
# Clamping inputs to /Domain and outputs to /Range
# ====================================================================


def test_input_clamped_to_domain() -> None:
    samples = [0, 255]
    kw = dict(domain=[0.0, 1.0], range_=[0.0, 1.0], size=[2], bits=8, samples=samples)
    fn = _build_type0(**kw)
    # Below and above domain clamp to endpoints.
    _assert_close(fn.eval([-5.0]), [0.0])
    _assert_close(fn.eval([5.0]), [1.0])


def test_output_clamped_to_range() -> None:
    # Decode pushes the value outside /Range; eval must clamp.
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2],
        bits=8,
        samples=[0, 255],
        decode=[-10.0, 10.0],
    )
    fn = _build_type0(**kw)
    # sample 0 → decode -10 → clamp to 0; sample 255 → decode 10 → clamp to 1.
    _assert_close(fn.eval([0.0]), [0.0])
    _assert_close(fn.eval([1.0]), [1.0])


# ====================================================================
# interpolate() helper exactness
# ====================================================================


@pytest.mark.parametrize(
    "x,xmin,xmax,ymin,ymax,expected",
    [
        (0.5, 0.0, 1.0, 0.0, 10.0, 5.0),
        (0.0, 0.0, 1.0, 2.0, 8.0, 2.0),
        (1.0, 0.0, 1.0, 2.0, 8.0, 8.0),
        (5.0, 0.0, 10.0, 100.0, 200.0, 150.0),
        (3.0, 0.0, 10.0, -10.0, 10.0, -4.0),
    ],
    ids=["mid", "lo", "hi", "halfup", "neg"],
)
def test_interpolate_helper(x, xmin, xmax, ymin, ymax, expected) -> None:
    assert PDFunction.interpolate(x, xmin, xmax, ymin, ymax) == pytest.approx(expected)


def test_interpolate_degenerate_domain_returns_ymin() -> None:
    # x_range_max == x_range_min → returns y_range_min (no div-by-zero).
    assert PDFunction.interpolate(5.0, 3.0, 3.0, 7.0, 9.0) == 7.0


# ====================================================================
# Boundary inputs → first/last sample
# ====================================================================


def test_boundary_inputs_hit_edge_samples() -> None:
    samples = [11, 22, 33, 44, 55]
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[5],
        bits=8,
        samples=samples,
        decode=[0.0, 255.0],
    )
    fn = _build_type0(**kw)
    _assert_close(fn.eval([0.0]), [11.0])  # first sample
    _assert_close(fn.eval([1.0]), [55.0])  # last sample


def test_nonzero_domain_boundaries() -> None:
    samples = [0, 128, 255]
    kw = dict(
        domain=[-10.0, 10.0],
        range_=[0.0, 255.0],
        size=[3],
        bits=8,
        samples=samples,
        decode=[0.0, 255.0],
    )
    fn = _build_type0(**kw)
    _assert_close(fn.eval([-10.0]), [0.0])
    _assert_close(fn.eval([0.0]), [128.0])
    _assert_close(fn.eval([10.0]), [255.0])


# ====================================================================
# Size = 1 degenerate dimension
# ====================================================================


def test_size_one_degenerate_returns_single_sample() -> None:
    # Only one grid point; any input maps to it.
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 255.0],
        size=[1],
        bits=8,
        samples=[123],
        decode=[0.0, 255.0],
    )
    fn = _build_type0(**kw)
    for x in (0.0, 0.5, 1.0):
        _assert_close(fn.eval([x]), [123.0])


def test_size_one_in_one_dim_of_2d() -> None:
    # 2D grid where dim 1 is degenerate (Size=1): bilinear collapses to 1D.
    samples = [0, 255]  # cells: (0,0)=0, (1,0)=255
    kw = dict(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 255.0],
        size=[2, 1],
        bits=8,
        samples=samples,
        decode=[0.0, 255.0],
    )
    fn = _build_type0(**kw)
    for x0 in (0.0, 0.5, 1.0):
        for x1 in (0.0, 1.0):
            _assert_close(fn.eval([x0, x1]), _ref_eval([x0, x1], **kw))


# ====================================================================
# 16/24/32-bit wide samples through decode
# ====================================================================


@pytest.mark.parametrize("bits", [16, 24])
def test_wide_sample_decode(bits: int) -> None:
    smax = (1 << bits) - 1
    samples = [0, smax]
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2],
        bits=bits,
        samples=samples,
        decode=[0.0, 1.0],
    )
    fn = _build_type0(**kw)
    _assert_close(fn.eval([0.0]), [0.0])
    _assert_close(fn.eval([1.0]), [1.0], tol=1e-6)
    _assert_close(fn.eval([0.5]), [0.5], tol=1e-6)


def test_32bit_top_bit_sign_extension_then_range_clamp() -> None:
    # A 32-bit code >= 2^31 is sign-extended to negative (upstream Java cast),
    # then Decode-mapped and clamped to /Range.
    code = 0x80000000  # 2^31, sign-extends to -2^31.
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2],
        bits=32,
        samples=[0, code],
        decode=[0.0, 1.0],
    )
    fn = _build_type0(**kw)
    # At x=1 the negative sample decodes negative, clamps to range min 0.
    _assert_close(fn.eval([1.0]), _ref_eval([1.0], **kw))
    _assert_close(fn.eval([1.0]), [0.0])


def test_32bit_below_signbit_unsigned() -> None:
    # A 32-bit code < 2^31 stays positive (no sign extension).
    code = 0x40000000  # 2^30
    kw = dict(
        domain=[0.0, 1.0],
        range_=[0.0, 4.0],
        size=[2],
        bits=32,
        samples=[0, code],
        decode=[0.0, 4.0],
    )
    fn = _build_type0(**kw)
    # code / (2^32-1) * 4 ≈ 1.0 (2^30 is a quarter of 2^32).
    _assert_close(fn.eval([1.0]), _ref_eval([1.0], **kw))
    expected = code / (2**32 - 1) * 4.0
    _assert_close(fn.eval([1.0]), [expected])
