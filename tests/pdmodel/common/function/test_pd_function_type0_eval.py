"""Hand-written eval coverage for ``PDFunctionType0`` (sampled-table).

Synthesises 1D and 2D sample-table dictionaries at multiple
``/BitsPerSample`` widths and exercises the encode/clamp/n-linear-interp/
decode pipeline mandated by PDF 32000-1 §7.10.2 and mirrored from
``org.apache.pdfbox.pdmodel.common.function.PDFunctionType0.eval``.

Sample bit-stream packing follows the upstream convention: successive
sample codes are adjacent in the bit stream with no padding at byte
boundaries; bits are MSB-first per PDF spec p.171.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType0


# ---------- helpers ----------


def _pack_samples(values: list[int], bits: int) -> bytes:
    """MSB-first bit-stream pack of ``values`` at ``bits`` width per sample.

    Mirrors upstream's ``MemoryCacheImageInputStream.readBits`` layout —
    successive samples are adjacent in the bit stream; the final byte is
    zero-padded on the low side if the total bit count is not a byte
    multiple.
    """
    total_bits = len(values) * bits
    big = 0
    for v in values:
        big = (big << bits) | (v & ((1 << bits) - 1))
    # Left-shift the low end so the first sample sits at the high end of
    # byte 0 (MSB-first packing).
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


# ---------- 1D linear interpolation ----------


def test_eval_1d_8bit_linear_at_corners() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        # Default /Decode = /Range -> sample 0/255 -> 0.0, 255 -> 1.0.
        samples=[0, 128, 255],
    )
    assert fn.eval([0.0])[0] == pytest.approx(0.0, abs=1e-9)
    assert fn.eval([1.0])[0] == pytest.approx(1.0, abs=1e-9)


def test_eval_1d_8bit_linear_at_midpoint() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        samples=[0, 128, 255],
    )
    # x=0.5 -> encoded=1.0 (exact grid index) -> sample[1]=128 -> 128/255.
    assert fn.eval([0.5])[0] == pytest.approx(128.0 / 255.0, abs=1e-9)


def test_eval_1d_8bit_linear_between_grid_points() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        samples=[0, 128, 255],
    )
    # x=0.25 -> encoded=0.5 -> 0.5*(0)+0.5*(128)=64 -> 64/255.
    assert fn.eval([0.25])[0] == pytest.approx(64.0 / 255.0, abs=1e-9)
    # x=0.75 -> encoded=1.5 -> 0.5*(128)+0.5*(255)=191.5 -> 191.5/255.
    assert fn.eval([0.75])[0] == pytest.approx(191.5 / 255.0, abs=1e-9)


def test_eval_1d_clips_input_below_domain() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        samples=[10, 128, 255],
    )
    # Below /Domain -> clipped to 0.0 -> sample[0] = 10/255.
    assert fn.eval([-5.0])[0] == pytest.approx(10.0 / 255.0, abs=1e-9)


def test_eval_1d_clips_input_above_domain() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        samples=[10, 128, 200],
    )
    # Above /Domain -> clipped to 1.0 -> sample[2] = 200/255.
    assert fn.eval([99.0])[0] == pytest.approx(200.0 / 255.0, abs=1e-9)


# ---------- /Decode override ----------


def test_eval_decode_remaps_sample_to_arbitrary_range() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[-1.0, 1.0],
        size=[3],
        bits=8,
        samples=[0, 128, 255],
        decode=[-1.0, 1.0],
    )
    # x=0 -> sample 0 -> decoded -1.0; x=1 -> sample 255 -> decoded +1.0.
    assert fn.eval([0.0])[0] == pytest.approx(-1.0, abs=1e-9)
    assert fn.eval([1.0])[0] == pytest.approx(1.0, abs=1e-9)
    # Mid grid -> sample 128 -> 128/255 of [-1,1] = -1 + 2*128/255.
    assert fn.eval([0.5])[0] == pytest.approx(-1.0 + 2.0 * 128.0 / 255.0, abs=1e-9)


# ---------- /Encode override ----------


def test_eval_encode_reverses_grid() -> None:
    """Reversed /Encode: domain max -> grid index 0, domain min -> last."""
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        samples=[0, 128, 255],
        encode=[2.0, 0.0],  # x=0 -> grid 2; x=1 -> grid 0
    )
    assert fn.eval([0.0])[0] == pytest.approx(255.0 / 255.0, abs=1e-9)
    assert fn.eval([1.0])[0] == pytest.approx(0.0, abs=1e-9)


# ---------- non-byte-aligned bits ----------


def test_eval_1d_4bit_samples() -> None:
    # /BitsPerSample=4: max 15. Two samples per byte, MSB-first.
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 15.0],
        size=[4],
        bits=4,
        samples=[0, 5, 10, 15],
    )
    assert fn.eval([0.0])[0] == pytest.approx(0.0, abs=1e-9)
    assert fn.eval([1.0 / 3.0])[0] == pytest.approx(5.0, abs=1e-9)
    assert fn.eval([1.0])[0] == pytest.approx(15.0, abs=1e-9)


def test_eval_1d_2bit_samples() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 3.0],
        size=[4],
        bits=2,
        samples=[0, 1, 2, 3],
    )
    assert fn.eval([0.0])[0] == pytest.approx(0.0, abs=1e-9)
    assert fn.eval([1.0])[0] == pytest.approx(3.0, abs=1e-9)


def test_eval_1d_1bit_samples() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[8],
        bits=1,
        samples=[0, 1, 0, 1, 0, 1, 0, 1],
    )
    assert fn.eval([0.0])[0] == pytest.approx(0.0, abs=1e-9)
    # Encoded x=1.0 -> grid 7 -> sample 1.
    assert fn.eval([1.0])[0] == pytest.approx(1.0, abs=1e-9)


def test_eval_1d_12bit_samples() -> None:
    """/BitsPerSample=12 must round-trip — upstream supports it via
    ``MemoryCacheImageInputStream.readBits(12)``."""
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 4095.0],
        size=[4],
        bits=12,
        samples=[0, 1024, 2048, 4095],
    )
    assert fn.eval([0.0])[0] == pytest.approx(0.0, abs=1e-9)
    assert fn.eval([1.0 / 3.0])[0] == pytest.approx(1024.0, abs=1e-9)
    assert fn.eval([2.0 / 3.0])[0] == pytest.approx(2048.0, abs=1e-9)
    assert fn.eval([1.0])[0] == pytest.approx(4095.0, abs=1e-9)


def test_eval_1d_16bit_samples() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 65535.0],
        size=[3],
        bits=16,
        samples=[0, 32768, 65535],
    )
    assert fn.eval([0.0])[0] == pytest.approx(0.0, abs=1e-9)
    assert fn.eval([0.5])[0] == pytest.approx(32768.0, abs=1e-9)
    assert fn.eval([1.0])[0] == pytest.approx(65535.0, abs=1e-9)


# ---------- 2D bilinear interpolation ----------


def test_eval_2d_8bit_at_corners() -> None:
    """2x2 grid, samples laid out with first dim varying fastest:
       cell index = x + y * sizeX.
       (0,0)=0  (1,0)=255
       (0,1)=255  (1,1)=0
    """
    fn = _build_type0(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2, 2],
        bits=8,
        samples=[0, 255, 255, 0],
    )
    assert fn.eval([0.0, 0.0])[0] == pytest.approx(0.0, abs=1e-9)
    assert fn.eval([1.0, 0.0])[0] == pytest.approx(1.0, abs=1e-9)
    assert fn.eval([0.0, 1.0])[0] == pytest.approx(1.0, abs=1e-9)
    assert fn.eval([1.0, 1.0])[0] == pytest.approx(0.0, abs=1e-9)


def test_eval_2d_8bit_at_center_is_bilinear_average() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2, 2],
        bits=8,
        samples=[0, 255, 255, 0],
    )
    # Bilinear midpoint: average of 0+255+255+0 / 4 = 127.5/255.
    assert fn.eval([0.5, 0.5])[0] == pytest.approx(127.5 / 255.0, abs=1e-9)


def test_eval_2d_8bit_along_edge() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2, 2],
        bits=8,
        samples=[0, 255, 255, 0],
    )
    # Along x at y=0: linear from 0 -> 255 across x.
    assert fn.eval([0.5, 0.0])[0] == pytest.approx(127.5 / 255.0, abs=1e-9)
    # Along y at x=0: linear from 0 -> 255 across y.
    assert fn.eval([0.0, 0.5])[0] == pytest.approx(127.5 / 255.0, abs=1e-9)


# ---------- multi-output ----------


def test_eval_multi_output() -> None:
    """1-input, 3-output (RGB-ish) sample table. Two grid points each
    carrying an (R, G, B) triple at 8 bits per channel."""
    # Cells laid out per spec: cell0 outputs first, then cell1's outputs.
    # cell0 = (0, 0, 0); cell1 = (255, 128, 64).
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        size=[2],
        bits=8,
        samples=[0, 0, 0, 255, 128, 64],
    )
    out = fn.eval([0.0])
    assert out == pytest.approx([0.0, 0.0, 0.0], abs=1e-9)
    out = fn.eval([1.0])
    assert out == pytest.approx([1.0, 128.0 / 255.0, 64.0 / 255.0], abs=1e-9)
    # Midpoint -> linear blend of both cells per channel.
    out = fn.eval([0.5])
    assert out == pytest.approx(
        [127.5 / 255.0, 64.0 / 255.0, 32.0 / 255.0], abs=1e-9
    )


# ---------- /Range output clipping ----------


def test_eval_clips_output_to_range() -> None:
    """When /Decode would emit values outside /Range, the result clips."""
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],  # tighter than /Decode's reach
        size=[2],
        bits=8,
        samples=[0, 255],
        decode=[-1.0, 2.0],  # 0 -> -1, 255 -> 2; both outside /Range
    )
    # x=0 sample=0 -> decoded -1 -> clipped to 0.
    assert fn.eval([0.0])[0] == pytest.approx(0.0, abs=1e-9)
    # x=1 sample=255 -> decoded 2 -> clipped to 1.
    assert fn.eval([1.0])[0] == pytest.approx(1.0, abs=1e-9)


# ---------- /Order = 3 (cubic) ----------


def test_eval_cubic_order_at_grid_points_matches_samples() -> None:
    """Cubic Catmull-Rom at integer-coord points returns the exact sample."""
    fn = _build_type0(
        domain=[0.0, 4.0],
        range_=[0.0, 255.0],
        size=[5],
        bits=8,
        samples=[0, 64, 128, 192, 255],
        order=3,
    )
    # At each integer grid point the cubic Hermite must reproduce the sample.
    for i, expected in enumerate([0.0, 64.0, 128.0, 192.0, 255.0]):
        assert fn.eval([float(i)])[0] == pytest.approx(expected, abs=1e-9)


def test_eval_cubic_order_unknown_falls_back_to_linear() -> None:
    """Unknown /Order values silently fall back to linear interp."""
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2],
        bits=8,
        samples=[0, 255],
        order=7,  # unsupported -> fallback
    )
    # Linear fallback at x=0.5 gives the average.
    assert fn.eval([0.5])[0] == pytest.approx(127.5 / 255.0, abs=1e-9)


# ---------- error paths ----------


def test_eval_unsupported_bits_raises() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    domain_arr = COSArray()
    domain_arr.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain_arr)
    range_arr = COSArray()
    range_arr.set_float_array([0.0, 1.0])
    raw.set_item("Range", range_arr)
    size_arr = COSArray()
    size_arr.add(COSFloat(2.0))
    raw.set_item("Size", size_arr)
    raw.set_int("BitsPerSample", 7)  # invalid
    raw.set_data(b"\x00\x00")
    fn = PDFunctionType0(raw)
    with pytest.raises(ValueError):
        fn.eval([0.5])


def test_eval_missing_size_raises() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    domain_arr = COSArray()
    domain_arr.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain_arr)
    range_arr = COSArray()
    range_arr.set_float_array([0.0, 1.0])
    raw.set_item("Range", range_arr)
    raw.set_int("BitsPerSample", 8)
    raw.set_data(b"\x00\xff")
    fn = PDFunctionType0(raw)
    with pytest.raises(ValueError):
        fn.eval([0.5])


# ---------- decode_sample_grid helper ----------


def test_decode_sample_grid_round_trips_1d() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[4],
        bits=8,
        samples=[7, 23, 91, 255],
    )
    grid = fn.decode_sample_grid()
    assert [row[0] for row in grid] == [7.0, 23.0, 91.0, 255.0]


def test_decode_sample_grid_round_trips_2d_first_dim_fastest() -> None:
    """2D layout: cell index = x + y * sizeX. With samples
       [a, b, c, d] across a 2x2 grid we must recover (0,0)=a, (1,0)=b,
       (0,1)=c, (1,1)=d (first dim varies fastest)."""
    fn = _build_type0(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2, 2],
        bits=8,
        samples=[10, 20, 30, 40],
    )
    grid = fn.decode_sample_grid()
    # grid[0] -> coord (0,0) -> 10; grid[1] -> (1,0) -> 20; grid[2] ->
    # (0,1) -> 30; grid[3] -> (1,1) -> 40.
    assert [row[0] for row in grid] == [10.0, 20.0, 30.0, 40.0]


def test_decode_sample_grid_12bit_round_trip() -> None:
    fn = _build_type0(
        domain=[0.0, 1.0],
        range_=[0.0, 4095.0],
        size=[3],
        bits=12,
        samples=[1, 2049, 4095],
    )
    grid = fn.decode_sample_grid()
    assert [row[0] for row in grid] == [1.0, 2049.0, 4095.0]
