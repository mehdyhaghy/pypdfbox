"""Wave 1369 — PDFunctionType0 ``/BitsPerSample`` matrix coverage.

Exercises every supported ``/BitsPerSample`` width listed in PDF 32000-1
§7.10.2 Table 38 — ``{1, 2, 4, 8, 12, 16, 24, 32}`` — at end-points and at
an interior cell so the MSB-first bit-stream unpacker in
``PDFunctionType0._read_sample`` is verified across all eight widths.

Hand-written tests for the 24 / 32-bit widths in particular were missing
from the existing ``test_pd_function_type0_eval.py`` matrix (which stopped
at 16 bits); this file closes that gap and adds a parametric matrix that
walks the corners + a midpoint sample for every width so future bit-stream
regressions are caught at the narrowest possible test.

Sample bit-stream packing follows the same MSB-first convention as the
sibling eval-test helpers — successive sample codes are adjacent in the
bit stream with no padding at byte boundaries.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType0


def _pack_samples(values: list[int], bits: int) -> bytes:
    """MSB-first bit-stream pack — bits are adjacent, no byte padding
    between samples; the final byte is zero-padded on the low side."""
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
    bits: int,
    samples: list[int],
    size: list[int] | None = None,
    decode: list[float] | None = None,
) -> PDFunctionType0:
    size = size if size is not None else [len(samples)]
    raw = COSStream()
    raw.set_int("FunctionType", 0)

    domain_arr = COSArray()
    domain_arr.set_float_array([0.0, 1.0] * len(size))
    raw.set_item("Domain", domain_arr)

    sample_max = (1 << bits) - 1
    # Decode maps the raw sample code [0, sample_max] linearly into the
    # /Range output domain. Defaulting to [0, sample_max] keeps the eval
    # result equal to the raw sample code so the unpacker is what's under
    # test (not the decode arithmetic).
    range_arr = COSArray()
    range_arr.set_float_array([0.0, float(sample_max)])
    raw.set_item("Range", range_arr)

    size_arr = COSArray()
    for s in size:
        size_arr.add(COSFloat(float(s)))
    raw.set_item("Size", size_arr)

    raw.set_int("BitsPerSample", bits)

    if decode is not None:
        dec = COSArray()
        dec.set_float_array(decode)
        raw.set_item("Decode", dec)

    raw.set_data(_pack_samples(samples, bits))
    return PDFunctionType0(raw)


# ---------- Parametric matrix: width -> (low, mid, high) round-trip ----------

# Each row: (bits, samples_for_a_3-cell_1D_table) — low / mid / high are
# (0, sample_max / 2, sample_max) so the decoded eval at the grid points
# is (0.0, sample_max / 2, sample_max).
_BIT_WIDTH_CASES = [
    (1, [0, 0, 1]),  # only 0 / 1 representable; "midpoint" is 0
    (2, [0, 1, 3]),  # sample_max = 3
    (4, [0, 7, 15]),  # sample_max = 15
    (8, [0, 127, 255]),
    (12, [0, 2047, 4095]),
    (16, [0, 32767, 65535]),
    (24, [0, 8388607, 16777215]),
    (32, [0, 2147483647, 4294967295]),
]


@pytest.mark.parametrize(
    ("bits", "samples"),
    _BIT_WIDTH_CASES,
    ids=[f"bits-{b}" for b, _ in _BIT_WIDTH_CASES],
)
def test_eval_endpoints_match_packed_samples(bits: int, samples: list[int]) -> None:
    """Eval at x=0 must read sample[0]; eval at x=1 must read sample[-1].

    Across all eight supported widths, the MSB-first unpacker must agree
    with what was packed into the bit stream.
    """
    fn = _build(bits=bits, samples=samples)
    assert math.isclose(fn.eval([0.0])[0], float(samples[0]), rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([1.0])[0], float(samples[-1]), rel_tol=1e-9, abs_tol=1e-9)


@pytest.mark.parametrize(
    ("bits", "samples"),
    _BIT_WIDTH_CASES,
    ids=[f"bits-{b}" for b, _ in _BIT_WIDTH_CASES],
)
def test_eval_interior_grid_point_matches_middle_sample(
    bits: int, samples: list[int]
) -> None:
    """Eval at the exact interior grid point reads the middle sample
    code — no interpolation across the cells when the encoded coordinate
    lands exactly on a grid index.
    """
    fn = _build(bits=bits, samples=samples)
    # The 3-cell grid spans encoded coords [0, 2]; x=0.5 maps to encoded 1.
    assert math.isclose(
        fn.eval([0.5])[0], float(samples[1]), rel_tol=1e-9, abs_tol=1e-9
    )


# ---------- Linear-interp midpoint between two corner samples ----------

@pytest.mark.parametrize(
    ("bits", "samples", "expected_mid"),
    [
        (4, [0, 15], 7.5),
        (8, [0, 255], 127.5),
        (12, [0, 4095], 2047.5),
        (16, [0, 65535], 32767.5),
        (24, [0, 16777215], 8388607.5),
        (32, [0, 4294967295], 2147483647.5),
    ],
    ids=[
        "linear-mid-4bit",
        "linear-mid-8bit",
        "linear-mid-12bit",
        "linear-mid-16bit",
        "linear-mid-24bit",
        "linear-mid-32bit",
    ],
)
def test_linear_midpoint_blends_corner_samples(
    bits: int, samples: list[int], expected_mid: float
) -> None:
    """A 2-cell table with samples ``[0, sample_max]`` linearly blends to
    ``sample_max / 2`` at the midpoint — independent of bit width."""
    fn = _build(bits=bits, samples=samples)
    out = fn.eval([0.5])[0]
    assert math.isclose(out, expected_mid, rel_tol=1e-9, abs_tol=1e-9)


# ---------- 2D table at each width — first-input-dim varies fastest ----------


@pytest.mark.parametrize(
    "bits",
    [1, 2, 4, 8, 12, 16, 24, 32],
    ids=[f"2d-bits-{b}" for b in [1, 2, 4, 8, 12, 16, 24, 32]],
)
def test_2d_table_first_dim_varies_fastest(bits: int) -> None:
    """A 2x2 table with samples [a, b, c, d] places ``a`` at (0,0), ``b``
    at (1,0), ``c`` at (0,1), ``d`` at (1,1) — confirms the row-major
    layout described in §7.10.2."""
    sample_max = (1 << bits) - 1
    # Use distinct values where possible — 1-bit only has 0/1 so all four
    # corners can't be unique, but the alternating pattern still locates
    # the per-axis dispatch.
    if bits == 1:
        samples = [0, 1, 1, 0]
        expected = [(0.0, 0.0, 0.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0), (1.0, 1.0, 0.0)]
    else:
        a, b, c, d = 0, sample_max // 4, sample_max // 2, sample_max
        samples = [a, b, c, d]
        expected = [
            (0.0, 0.0, float(a)),
            (1.0, 0.0, float(b)),
            (0.0, 1.0, float(c)),
            (1.0, 1.0, float(d)),
        ]
    fn = _build(bits=bits, samples=samples, size=[2, 2])
    for x, y, want in expected:
        got = fn.eval([x, y])[0]
        assert math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-9), (
            f"bits={bits} at ({x}, {y}) got {got} want {want}"
        )


# ---------- Unsupported bit widths reject ----------


@pytest.mark.parametrize(
    "bits",
    [0, 3, 5, 6, 7, 9, 11, 17, 33, 64],
    ids=[f"reject-bits-{b}" for b in [0, 3, 5, 6, 7, 9, 11, 17, 33, 64]],
)
def test_eval_rejects_unsupported_bits_per_sample(bits: int) -> None:
    """PDF 32000-1 §7.10.2 Table 38 only lists ``{1, 2, 4, 8, 12, 16, 24,
    32}`` — every other value must raise ``ValueError`` at eval time."""
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain)
    range_arr = COSArray()
    range_arr.set_float_array([0.0, 1.0])
    raw.set_item("Range", range_arr)
    size_arr = COSArray()
    size_arr.add(COSFloat(2.0))
    raw.set_item("Size", size_arr)
    raw.set_int("BitsPerSample", bits)
    raw.set_data(b"\x00\x00\x00\x00")
    fn = PDFunctionType0(raw)
    with pytest.raises(ValueError, match="BitsPerSample"):
        fn.eval([0.0])
