"""Hand-written coverage for ``PDFunctionType0`` accessors and round-out
methods (``set_size`` / ``set_bits_per_sample`` / ``set_order`` /
``set_encode`` / ``set_decode`` / ``get_samples``) plus a 1-in/1-out and
a 2-in/3-out ``eval`` parity check.

Pre-existing eval coverage (clipping, /Encode reversal, multi-bit widths,
cubic /Order, output clipping, error paths) lives in
``test_pd_function_type0_eval.py``; this file deliberately does not
duplicate that surface — it focuses on the round-out work added in this
wave.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType0


def _pack_samples(values: list[int], bits: int) -> bytes:
    """MSB-first bit-stream pack — matches the eval-test helper so layout
    is consistent across the two test files."""
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


# ---------- function-type identity ----------


def test_get_function_type_is_zero() -> None:
    fn = PDFunctionType0()
    assert fn.get_function_type() == 0
    assert fn.is_function_type_0() is True


# ---------- accessor defaults ----------


def test_default_order_is_one() -> None:
    """PDF 32000-1 §7.10.2: ``/Order`` defaults to 1 when absent."""
    fn = PDFunctionType0()
    assert fn.get_order() == 1


def test_default_size_encode_decode_are_none_when_absent() -> None:
    fn = PDFunctionType0()
    assert fn.get_size() is None
    assert fn.get_encode() is None
    assert fn.get_decode() is None
    # /BitsPerSample falls back to 0 when absent (rejected by eval).
    assert fn.get_bits_per_sample() == 0


# ---------- setters ----------


def test_set_size_round_trips() -> None:
    fn = PDFunctionType0()
    arr = COSArray()
    arr.add(COSFloat(4.0))
    arr.add(COSFloat(3.0))
    fn.set_size(arr)
    got = fn.get_size()
    assert got is arr
    assert got.size() == 2


def test_set_size_none_removes_entry() -> None:
    fn = PDFunctionType0()
    arr = COSArray()
    arr.add(COSFloat(2.0))
    fn.set_size(arr)
    fn.set_size(None)
    assert fn.get_size() is None


def test_set_bits_per_sample_round_trips() -> None:
    fn = PDFunctionType0()
    fn.set_bits_per_sample(12)
    assert fn.get_bits_per_sample() == 12


def test_set_order_round_trips() -> None:
    fn = PDFunctionType0()
    fn.set_order(3)
    assert fn.get_order() == 3


def test_set_encode_round_trips_then_clears() -> None:
    fn = PDFunctionType0()
    enc = COSArray()
    enc.set_float_array([0.0, 5.0, 1.0, 6.0])
    fn.set_encode(enc)
    assert fn.get_encode() is enc
    fn.set_encode(None)
    assert fn.get_encode() is None


def test_set_decode_round_trips_then_clears() -> None:
    fn = PDFunctionType0()
    dec = COSArray()
    dec.set_float_array([-1.0, 1.0])
    fn.set_decode(dec)
    assert fn.get_decode() is dec
    fn.set_decode(None)
    assert fn.get_decode() is None


# ---------- upstream-named aliases ----------


def test_set_encode_values_alias_round_trips() -> None:
    """``set_encode_values`` mirrors upstream PDFBox ``setEncodeValues``."""
    fn = PDFunctionType0()
    enc = COSArray()
    enc.set_float_array([0.0, 5.0])
    fn.set_encode_values(enc)
    assert fn.get_encode() is enc
    fn.set_encode_values(None)
    assert fn.get_encode() is None


def test_set_decode_values_alias_round_trips() -> None:
    """``set_decode_values`` mirrors upstream PDFBox ``setDecodeValues``."""
    fn = PDFunctionType0()
    dec = COSArray()
    dec.set_float_array([-1.0, 1.0])
    fn.set_decode_values(dec)
    assert fn.get_decode() is dec
    fn.set_decode_values(None)
    assert fn.get_decode() is None


# ---------- get_encode_values / get_decode_values (resolved arrays) ----------


def test_get_encode_values_returns_explicit_array() -> None:
    """When ``/Encode`` is set explicitly, ``get_encode_values`` returns
    that array as-is."""
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[4, 4],
        bits=8,
        samples=[0] * 16,
        encode=[0.0, 3.0, 1.0, 2.0],
    )
    encode = fn.get_encode_values()
    assert encode is not None
    assert encode.to_float_array() == [0.0, 3.0, 1.0, 2.0]


def test_get_encode_values_defaults_to_size_minus_one_per_dim() -> None:
    """When ``/Encode`` is absent the default per PDF 32000-1 Table 38 is
    ``[0 (Size[0]-1) 0 (Size[1]-1) ...]`` — mirrors PDFBox
    ``getEncodeValues`` (PDFunctionType0.java:144-163)."""
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[4, 8],
        bits=8,
        samples=[0] * 32,
    )
    encode = fn.get_encode_values()
    assert encode is not None
    assert encode.to_float_array() == [0.0, 3.0, 0.0, 7.0]


def test_get_encode_values_returns_none_when_size_absent() -> None:
    fn = PDFunctionType0()
    assert fn.get_encode_values() is None


def test_get_decode_values_returns_explicit_array() -> None:
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0, 0.0, 1.0],
        size=[2],
        bits=8,
        samples=[0, 0],
        decode=[-2.0, 2.0, -3.0, 3.0],
    )
    decode = fn.get_decode_values()
    assert decode is not None
    assert decode.to_float_array() == [-2.0, 2.0, -3.0, 3.0]


def test_get_decode_values_defaults_to_range_array() -> None:
    """When ``/Decode`` is absent, ``get_decode_values`` falls back to the
    function's ``/Range`` array (PDFunctionType0.java:170-182)."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[-5.0, 5.0, -10.0, 10.0],
        size=[2],
        bits=8,
        samples=[0, 0],
    )
    decode = fn.get_decode_values()
    assert decode is not None
    assert decode.to_float_array() == [-5.0, 5.0, -10.0, 10.0]


# ---------- get_encode_for_parameter / get_decode_for_parameter ----------


def test_get_encode_for_parameter_explicit_pair() -> None:
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[4, 4],
        bits=8,
        samples=[0] * 16,
        encode=[0.0, 3.0, 0.0, 3.0],
    )
    assert fn.get_encode_for_parameter(0) == (0.0, 3.0)
    assert fn.get_encode_for_parameter(1) == (0.0, 3.0)


def test_get_encode_for_parameter_default_uses_size_minus_one() -> None:
    """When ``/Encode`` is absent, the default per PDF 32000-1 Table 38
    is ``(0, Size[i] - 1)`` for each input dimension."""
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[4, 8],
        bits=8,
        samples=[0] * 32,
    )
    assert fn.get_encode_for_parameter(0) == (0.0, 3.0)
    assert fn.get_encode_for_parameter(1) == (0.0, 7.0)


def test_get_encode_for_parameter_out_of_range_returns_none() -> None:
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[4],
        bits=8,
        samples=[0, 1, 2, 3],
    )
    assert fn.get_encode_for_parameter(-1) is None
    assert fn.get_encode_for_parameter(5) is None


def test_get_decode_for_parameter_explicit_pair() -> None:
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0, 0.0, 1.0],
        size=[2],
        bits=8,
        samples=[0, 0],
        decode=[-2.0, 2.0, -3.0, 3.0],
    )
    assert fn.get_decode_for_parameter(0) == (-2.0, 2.0)
    assert fn.get_decode_for_parameter(1) == (-3.0, 3.0)


def test_get_decode_for_parameter_default_falls_back_to_range() -> None:
    """When ``/Decode`` is absent the default is the function's ``/Range``
    pair for that output dimension (PDF 32000-1 Table 38)."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[-5.0, 5.0, -10.0, 10.0],
        size=[2],
        bits=8,
        samples=[0, 0],
    )
    assert fn.get_decode_for_parameter(0) == (-5.0, 5.0)
    assert fn.get_decode_for_parameter(1) == (-10.0, 10.0)


def test_get_decode_for_parameter_out_of_range_returns_none() -> None:
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2],
        bits=8,
        samples=[0, 0],
    )
    assert fn.get_decode_for_parameter(-1) is None
    assert fn.get_decode_for_parameter(2) is None


# ---------- get_samples (lazy decode) ----------


def test_get_samples_decodes_1d_8bit() -> None:
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[4],
        bits=8,
        samples=[7, 23, 91, 255],
    )
    samples = fn.get_samples()
    assert samples == [[7], [23], [91], [255]]


def test_get_samples_decodes_2d_first_dim_fastest() -> None:
    """Cell index = x + y * sizeX. Samples [a, b, c, d] across a 2x2
    grid -> (0,0)=a, (1,0)=b, (0,1)=c, (1,1)=d."""
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2, 2],
        bits=8,
        samples=[10, 20, 30, 40],
    )
    samples = fn.get_samples()
    assert samples == [[10], [20], [30], [40]]


def test_get_samples_multi_output() -> None:
    """1-input, 3-output (RGB-ish): two cells each carrying (R, G, B)."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        size=[2],
        bits=8,
        samples=[0, 0, 0, 255, 128, 64],
    )
    assert fn.get_samples() == [[0, 0, 0], [255, 128, 64]]


def test_get_samples_is_cached() -> None:
    """Repeat call returns the same list (identity, not just equality) —
    mirrors upstream's lazy-init field cache."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        samples=[0, 128, 255],
    )
    a = fn.get_samples()
    b = fn.get_samples()
    assert a is b


def test_get_samples_cache_invalidated_by_set_size() -> None:
    """Resetting ``/Size`` must invalidate the cached decoded grid."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        samples=[0, 128, 255],
    )
    fn.get_samples()  # prime the cache
    arr = COSArray()
    arr.add(COSFloat(2.0))
    fn.set_size(arr)
    # Underlying body still 3 bytes — but only 2 cells should appear.
    samples = fn.get_samples()
    assert len(samples) == 2


def test_get_samples_rejects_unsupported_bits() -> None:
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
        fn.get_samples()


# ---------- 1-in / 1-out eval parity ----------


def test_eval_1in_1out_parity_at_grid_and_midpoint() -> None:
    """Acceptance per task spec: 1-in/1-out function eval matches expected
    outputs at corners and at the midpoint of each cell."""
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[3],
        bits=8,
        samples=[0, 128, 255],
    )
    # Corners
    assert fn.eval([0.0])[0] == pytest.approx(0.0, abs=1e-9)
    assert fn.eval([1.0])[0] == pytest.approx(1.0, abs=1e-9)
    # Exact midpoint -> grid index 1 -> sample 128.
    assert fn.eval([0.5])[0] == pytest.approx(128.0 / 255.0, abs=1e-9)
    # Cell midpoints -> linear blend.
    assert fn.eval([0.25])[0] == pytest.approx(64.0 / 255.0, abs=1e-9)
    assert fn.eval([0.75])[0] == pytest.approx(191.5 / 255.0, abs=1e-9)


# ---------- 2-in / 3-out eval parity ----------


def test_eval_2in_3out_parity_at_corners_and_center() -> None:
    """Acceptance per task spec: 2-in/3-out function eval matches expected
    outputs. 2x2 grid carrying 3 channels per cell.

    Sample layout (first input dim varies fastest), per cell = (R, G, B):
      (0, 0) -> (  0,   0,   0)
      (1, 0) -> (255,   0,   0)
      (0, 1) -> (  0, 255,   0)
      (1, 1) -> (255, 255,   0)
    """
    fn = _build(
        domain=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        size=[2, 2],
        bits=8,
        samples=[
            0, 0, 0,
            255, 0, 0,
            0, 255, 0,
            255, 255, 0,
        ],
    )
    # Corners hit exact samples.
    assert fn.eval([0.0, 0.0]) == pytest.approx([0.0, 0.0, 0.0], abs=1e-9)
    assert fn.eval([1.0, 0.0]) == pytest.approx([1.0, 0.0, 0.0], abs=1e-9)
    assert fn.eval([0.0, 1.0]) == pytest.approx([0.0, 1.0, 0.0], abs=1e-9)
    assert fn.eval([1.0, 1.0]) == pytest.approx([1.0, 1.0, 0.0], abs=1e-9)
    # Centre is the bilinear average of all four corners per channel.
    centre = fn.eval([0.5, 0.5])
    assert centre == pytest.approx(
        [
            (0 + 255 + 0 + 255) / 4.0 / 255.0,
            (0 + 0 + 255 + 255) / 4.0 / 255.0,
            0.0,
        ],
        abs=1e-9,
    )
