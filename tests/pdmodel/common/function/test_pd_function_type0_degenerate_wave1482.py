"""Wave 1482 — PDFunctionType0 degenerate / boundary eval parity.

Differentially probed against live Apache PDFBox 3.0.7
(``FunctionType0DegenerateProbe`` / ``FunctionType0Bit32Probe``); every
expected literal below is the exact value PDFBox's ``PDFunctionType0.eval``
returns. Angles covered here that the wave-1369 matrix did not:

* ``/Size[i] == 1`` — the axis collapses to its single sample with no
  interpolation (upstream ``inPrev == inNext`` short-circuit in
  ``Rinterpol.rinterpol``).
* A 2-input table where one axis has ``/Size == 1`` while the other
  interpolates normally.
* Empty sample stream (zero-length body) — upstream allocates
  ``new int[arraySize][nOut]`` (zero-filled) and the failed read leaves
  every cell zero.
* Short / truncated sample stream — the present cells decode normally; the
  cells past the end of the body read as zero (upstream catches the
  ``IOException`` and returns the partially-filled, zero-initialised array).
* Input exactly at a non-``[0,1]`` /Domain boundary (and beyond it, to pin
  the clip).
* 1-bit and 2-bit packed widths at and between grid points.
* **32-bit signed-cast quirk** — upstream stores each code via
  ``(int) mciis.readBits(32)``; a code ``>= 2^31`` truncates to a NEGATIVE
  signed-32 int before the /Decode mapping, so it clamps to /Range[min].
  pypdfbox sign-extends 32-bit codes to match (see CHANGES.md).

These tests pin the literals WITHOUT the oracle (the oracle confirmed them
once; the values are frozen here). A companion @requires_oracle differential
test lives in ``oracle/test_function_type0_degenerate_oracle.py``.
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
    samples: list[int] | None = None,
    body: bytes | None = None,
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
    if body is not None:
        raw.set_data(body)
    else:
        assert samples is not None
        raw.set_data(_pack_samples(samples, bits))
    return PDFunctionType0(raw)


def _close(got: float, want: float) -> bool:
    return math.isclose(got, want, rel_tol=1e-6, abs_tol=1e-6)


# ---------- /Size[i] == 1 collapses to the single sample ----------


@pytest.mark.parametrize("x", [0.0, 0.5, 1.0])
def test_size_one_collapses_to_single_sample(x: float) -> None:
    """A 1-in 1-out table with /Size = [1] returns its only sample for
    every input — Encode default = [0 0], no neighbour to interpolate."""
    fn = _build(domain=[0, 1], range_=[0, 255], size=[1], bits=8, samples=[200])
    assert _close(fn.eval([x])[0], 200.0)


@pytest.mark.parametrize(
    ("inp", "want"),
    [
        ([0.0, 0.0], 10.0),
        ([0.5, 0.0], 10.0),
        ([0.0, 0.5], 20.0),
        ([1.0, 1.0], 30.0),
        ([0.3, 0.5], 20.0),
    ],
    ids=["00", "x-half", "y-half", "11", "x-third-y-half"],
)
def test_one_axis_size_one_collapses_other_interpolates(
    inp: list[float], want: float
) -> None:
    """/Size = [1, 3]: the first axis collapses (single sample), the second
    interpolates. Grid cells (0,0)=10 (0,1)=20 (0,2)=30. The x input is
    irrelevant; y picks/blends the column."""
    fn = _build(
        domain=[0, 1, 0, 1],
        range_=[0, 255],
        size=[1, 3],
        bits=8,
        samples=[10, 20, 30],
    )
    assert _close(fn.eval(inp)[0], want)


# ---------- empty / truncated sample stream ----------


@pytest.mark.parametrize("x", [0.0, 0.5, 1.0])
def test_empty_sample_stream_reads_zero(x: float) -> None:
    """A zero-length body yields an all-zero sample table — upstream
    allocates ``new int[][]`` (zero) and the read fails immediately."""
    fn = _build(domain=[0, 1], range_=[0, 255], size=[3], bits=8, body=b"")
    assert _close(fn.eval([x])[0], 0.0)


@pytest.mark.parametrize(
    ("x", "want"),
    [
        (0.0, 100.0),
        (0.25, 50.0),
        (0.5, 0.0),
        (0.75, 0.0),
        (1.0, 0.0),
    ],
    ids=["0", "quarter", "half", "three-quarter", "1"],
)
def test_truncated_sample_stream_zero_fills_tail(x: float, want: float) -> None:
    """A 3-cell 8-bit table needs 3 bytes but only 1 (=100) is supplied.
    sample[0]=100, sample[1]=sample[2]=0. x=0.25 maps to encoded 0.5 ->
    blend(100, 0) = 50."""
    fn = _build(
        domain=[0, 1], range_=[0, 255], size=[3], bits=8, body=bytes([100])
    )
    assert _close(fn.eval([x])[0], want)


# ---------- input exactly at a non-[0,1] domain boundary ----------


@pytest.mark.parametrize(
    ("x", "want"),
    [
        (-2.0, 0.0),  # lower domain boundary -> sample[0]
        (6.0, 160.0),  # upper domain boundary -> sample[4]
        (2.0, 80.0),  # mid -> exact grid point 2 -> sample[2]
        (-3.0, 0.0),  # below domain -> clips to -2
        (7.0, 160.0),  # above domain -> clips to 6
    ],
    ids=["lo-bound", "hi-bound", "mid", "below", "above"],
)
def test_input_at_and_beyond_domain_boundary(x: float, want: float) -> None:
    """/Domain = [-2, 6] over 5 evenly-spaced samples. Boundary inputs map
    to the end samples; out-of-domain inputs clip to the boundary first."""
    fn = _build(
        domain=[-2, 6],
        range_=[0, 255],
        size=[5],
        bits=8,
        samples=[0, 40, 80, 120, 160],
    )
    assert _close(fn.eval([x])[0], want)


# ---------- sub-8-bit packed widths ----------


@pytest.mark.parametrize(
    ("x", "want"),
    [
        (0.0, 0.0),
        (1.0 / 3.0, 1.0),
        (0.5, 1.0),
        (2.0 / 3.0, 1.0),
        (1.0, 0.0),
    ],
    ids=["0", "third", "half", "two-third", "1"],
)
def test_one_bit_width(x: float, want: float) -> None:
    """1-bit, 4 samples [0,1,1,0] over [0,1]. Grid points hit the codes;
    x=0.5 maps to encoded 1.5 -> blend(1, 1) = 1."""
    fn = _build(domain=[0, 1], range_=[0, 1], size=[4], bits=1, samples=[0, 1, 1, 0])
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize(
    ("x", "want"),
    [
        (0.0, 0.0),
        (0.25, 0.75),
        (0.5, 1.5),
        (0.75, 2.25),
        (1.0, 3.0),
    ],
    ids=["0", "quarter", "half", "three-quarter", "1"],
)
def test_two_bit_width(x: float, want: float) -> None:
    """2-bit, 4 samples [0,1,2,3] over [0,1], Range/Decode = [0,3]. Linear
    blend across the whole grid is x*3."""
    fn = _build(domain=[0, 1], range_=[0, 3], size=[4], bits=2, samples=[0, 1, 2, 3])
    assert _close(fn.eval([x])[0], want)


# ---------- 32-bit signed-cast quirk ----------


@pytest.mark.parametrize(
    ("samples", "range_", "inputs_wants"),
    [
        # high code 0x7FFFFFFF is positive as int -> normal linear blend.
        (
            [0, 0x7FFFFFFF],
            [-2, 2],
            [(0.0, -2.0), (0.25, -1.5), (0.5, -1.0), (0.75, -0.5), (1.0, 0.0)],
        ),
        # 0x80000000 sign-extends to Integer.MIN -> clamps to Range[min].
        (
            [0, 0x80000000],
            [-2, 2],
            [(0.0, -2.0), (0.5, -2.0), (1.0, -2.0)],
        ),
        # 0xFFFFFFFF sign-extends to -1 -> clamps to Range[min].
        (
            [0, 0xFFFFFFFF],
            [-2, 2],
            [(0.0, -2.0), (0.5, -2.0), (1.0, -2.0)],
        ),
        # both codes negative as int -> every input clamps to Range[min].
        (
            [0x80000000, 0xFFFFFFFF],
            [-2, 2],
            [(0.0, -2.0), (0.5, -2.0), (1.0, -2.0)],
        ),
        # wider range still clamps -1 to the floor (-5).
        (
            [0, 0xFFFFFFFF],
            [-5, 5],
            [(0.0, -5.0), (0.5, -5.0), (1.0, -5.0)],
        ),
    ],
    ids=["maxpos", "int-min", "neg-one", "both-neg", "wide-range"],
)
def test_thirty_two_bit_signed_cast(
    samples: list[int],
    range_: list[float],
    inputs_wants: list[tuple[float, float]],
) -> None:
    """Upstream stores each 32-bit code as ``(int) readBits(32)``; a code
    with the top bit set becomes a NEGATIVE signed int before /Decode, so it
    drives the output to (or below) Range[min] and clamps there. pypdfbox
    sign-extends to reproduce these exact values."""
    fn = _build(domain=[0, 1], range_=range_, size=[2], bits=32, samples=samples)
    for x, want in inputs_wants:
        assert _close(fn.eval([x])[0], want), f"x={x} samples={samples}"


def test_thirty_two_bit_default_range_clamps_to_zero() -> None:
    """The canonical [0, 0xFFFFFFFF] / Range=[0,1] case: the high sample
    sign-extends to -1, so the whole upper half maps below 0 and clamps to
    0 — eval returns 0 at x>=0.5, matching PDFBox."""
    fn = _build(
        domain=[0, 1],
        range_=[0, 1],
        size=[2],
        bits=32,
        samples=[0, 0xFFFFFFFF],
    )
    assert _close(fn.eval([0.0])[0], 0.0)
    assert _close(fn.eval([0.5])[0], 0.0)
    assert _close(fn.eval([1.0])[0], 0.0)


def test_thirty_two_bit_get_samples_is_signed() -> None:
    """``get_samples`` exposes the same signed-32 truncation upstream's
    ``int[][]`` table holds — a 0xFFFFFFFF code reads as -1, not
    4294967295."""
    fn = _build(
        domain=[0, 1],
        range_=[0, 1],
        size=[2],
        bits=32,
        samples=[0, 0xFFFFFFFF],
    )
    samples = fn.get_samples()
    assert samples == [[0], [-1]]
