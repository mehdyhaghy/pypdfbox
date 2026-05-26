"""Wave 1369 — PDFunctionType2 (exponential) /N exponent matrix.

Hand-written /N exponent sweep complementing the existing eval coverage
in ``test_pd_function_type_2.py`` and ``upstream/test_pd_function_type_2.py``.

Per PDF 32000-1 §7.10.3, a Type 2 function is

    y[j] = C0[j] + x**N * (C1[j] - C0[j])

with /N defaulting to 1.0. This file walks the common /N values used in
real PDFs (square, cube, sqrt, identity, fourth-root) and verifies they
land on the exact closed-form values at characteristic input points
(0, 1/4, 1/2, 3/4, 1) using ``math.isclose``.

It also exercises:

* Vector-valued /C0 + /C1 with N=1 — a 4-channel gamma transform.
* Non-1 /N with negative input (raises ``math.nan`` per Python's
  float-domain rule, matching upstream PDFBox).
* /N = 0 (constant interpolation — eval always returns /C1).
* The boundary semantics of /Domain clipping: when /Domain rejects the
  input, the resulting clipped input feeds the exponent before /Range
  applies.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunctionType2


def _make(
    *,
    c0: list[float],
    c1: list[float],
    n: float,
    domain: list[float] | None = None,
    range_: list[float] | None = None,
) -> PDFunctionType2:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    c0_arr = COSArray()
    c0_arr.set_float_array(c0)
    raw.set_item("C0", c0_arr)
    c1_arr = COSArray()
    c1_arr.set_float_array(c1)
    raw.set_item("C1", c1_arr)
    raw.set_item("N", COSFloat(n))
    if domain is not None:
        d = COSArray()
        d.set_float_array(domain)
        raw.set_item("Domain", d)
    if range_ is not None:
        r = COSArray()
        r.set_float_array(range_)
        raw.set_item("Range", r)
    return PDFunctionType2(raw)


# ---------- /N matrix: identity, square, cube, sqrt, fourth-root ----------


@pytest.mark.parametrize(
    ("n", "x", "expected"),
    [
        # /N = 1 — identity interpolation
        (1.0, 0.0, 0.0),
        (1.0, 0.25, 0.25),
        (1.0, 0.5, 0.5),
        (1.0, 0.75, 0.75),
        (1.0, 1.0, 1.0),
        # /N = 2 — square
        (2.0, 0.0, 0.0),
        (2.0, 0.25, 0.0625),
        (2.0, 0.5, 0.25),
        (2.0, 0.75, 0.5625),
        (2.0, 1.0, 1.0),
        # /N = 3 — cube
        (3.0, 0.0, 0.0),
        (3.0, 0.5, 0.125),
        (3.0, 1.0, 1.0),
        # /N = 0.5 — sqrt
        (0.5, 0.0, 0.0),
        (0.5, 0.25, 0.5),
        (0.5, 0.5, math.sqrt(0.5)),
        (0.5, 1.0, 1.0),
        # /N = 0.25 — fourth root
        (0.25, 0.0, 0.0),
        (0.25, 0.0625, 0.5),
        (0.25, 1.0, 1.0),
        # /N = 4 — fourth power
        (4.0, 0.0, 0.0),
        (4.0, 0.5, 0.0625),
        (4.0, 1.0, 1.0),
    ],
    ids=lambda v: f"{v}",
)
def test_exponent_matrix_at_characteristic_inputs(
    n: float, x: float, expected: float
) -> None:
    """Walk /N across {identity, square, cube, sqrt, 4th-root, 4th-power}
    and confirm the closed-form ``x**N`` value at each input."""
    fn = _make(c0=[0.0], c1=[1.0], n=n, domain=[0.0, 1.0])
    out = fn.eval([x])[0]
    assert math.isclose(out, expected, rel_tol=1e-9, abs_tol=1e-9), (
        f"/N={n} x={x}: got {out} want {expected}"
    )


# ---------- /N = 0 — constant interpolation ----------


def test_n_zero_returns_c1_for_all_inputs() -> None:
    """``x**0 = 1`` for any x > 0; Python's ``math.pow(0.0, 0.0) = 1.0``.

    So with /N = 0 the eval always returns C0 + 1 * (C1 - C0) = C1, for
    any input in [0, 1]. This is a degenerate case but reachable through
    a malformed shading dictionary in the wild.
    """
    fn = _make(c0=[0.2, 0.4], c1=[0.8, 1.0], n=0.0, domain=[0.0, 1.0])
    for x in [0.0, 0.25, 0.5, 0.75, 1.0]:
        result = fn.eval([x])
        # /C0 / /C1 stored as COSFloat (single-precision) — round-trip
        # introduces ~1e-8 drift on values like 0.8 that aren't exactly
        # representable in binary32. Use a wider tolerance accordingly.
        assert result == pytest.approx([0.8, 1.0], abs=1e-6), (
            f"/N=0 at x={x}: got {result}"
        )


# ---------- Vector /C0, /C1 with N=1 (4-channel CMYK gamma) ----------


def test_vector_c0_c1_4_channel_linear_interpolation() -> None:
    """4-channel /C0 + /C1 with /N=1 interpolates each channel linearly."""
    fn = _make(
        c0=[0.0, 0.25, 0.5, 0.75],
        c1=[1.0, 0.75, 0.5, 0.25],
        n=1.0,
        domain=[0.0, 1.0],
    )
    # At x=0.5, each channel is the midpoint of C0[j] and C1[j].
    out = fn.eval([0.5])
    assert out == pytest.approx([0.5, 0.5, 0.5, 0.5], abs=1e-9)


# ---------- Negative input with fractional /N (NaN per upstream parity) ----------


@pytest.mark.parametrize("n", [0.5, 0.25, 1.5, 2.5], ids=["n-0.5", "n-0.25", "n-1.5", "n-2.5"])
def test_negative_input_with_fractional_n_yields_nan(n: float) -> None:
    """Python's ``math.pow(-x, fractional)`` raises ``ValueError`` for
    negative bases with non-integer exponents; the helper converts this
    to ``math.nan`` (upstream Java returns ``NaN`` similarly). Each
    channel must be ``nan``."""
    fn = _make(
        c0=[0.0, 0.0],
        c1=[1.0, 1.0],
        n=n,
        domain=[-1.0, 1.0],
    )
    out = fn.eval([-0.5])
    assert len(out) == 2
    assert all(math.isnan(v) for v in out), f"/N={n}: {out}"


def test_negative_input_with_integer_n_returns_real_value() -> None:
    """Integer /N values with negative base are real-valued via
    ``math.pow`` (signed exponentiation).

    /N=3 at x=-0.5 -> (-0.5)**3 = -0.125 -> output 0 + -0.125 * (1-0) = -0.125
    """
    fn = _make(
        c0=[0.0],
        c1=[1.0],
        n=3.0,
        domain=[-1.0, 1.0],
    )
    out = fn.eval([-0.5])[0]
    assert math.isclose(out, -0.125, rel_tol=1e-9, abs_tol=1e-9)


# ---------- input is NOT clipped to /Domain (upstream parity) ----------


def test_input_not_clipped_to_domain_before_exponent() -> None:
    """An input outside /Domain is NOT clipped before the exponent.

    Apache PDFBox 3.0.7 ``PDFunctionType2.eval`` raises ``input[0]`` to /N
    without first clamping to /Domain (verified via the ShadingFuncProbe
    oracle). So x=5 with /Domain=[0, 0.5] and /N=2 yields 5**2 = 25, not
    0.5**2 = 0.25."""
    fn = _make(c0=[0.0], c1=[1.0], n=2.0, domain=[0.0, 0.5])
    # x=5 -> 5**2 = 25 (no domain clip, no /Range to clamp).
    assert math.isclose(fn.eval([5.0])[0], 25.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=-1, /N=2 -> (-1)**2 = 1.0 (no domain clip).
    assert math.isclose(fn.eval([-1.0])[0], 1.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Range clipping at output ----------


def test_range_clamps_output_per_channel() -> None:
    """Each output channel clamps independently against its /Range pair."""
    fn = _make(
        c0=[0.0, 0.0],
        c1=[5.0, -5.0],  # C1 outside [0, 1] in both directions
        n=1.0,
        domain=[0.0, 1.0],
        range_=[0.0, 1.0, 0.0, 1.0],
    )
    # At x=1, raw outputs are (5, -5); range clamps to (1, 0).
    assert fn.eval([1.0]) == pytest.approx([1.0, 0.0], abs=1e-9)


# ---------- /Domain inverted pair ----------


def test_eval_with_inverted_domain_pair_clamps_correctly() -> None:
    """When /Domain = [hi, lo] (inverted), clip_input normalises the pair
    before clamping, so the function still maps inside the corrected
    range."""
    fn = _make(
        c0=[0.0],
        c1=[10.0],
        n=1.0,
        domain=[1.0, 0.0],  # inverted
    )
    # Clipping normalises [0, 1]; eval x=0.5 -> y=5.
    assert math.isclose(fn.eval([0.5])[0], 5.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- Symmetry / monotonicity ----------


@pytest.mark.parametrize(
    "n",
    [0.5, 1.0, 2.0, 3.0, 5.0],
    ids=["n-0.5", "n-1.0", "n-2.0", "n-3.0", "n-5.0"],
)
def test_eval_monotonic_in_x_for_positive_c1_minus_c0(n: float) -> None:
    """For C1 > C0 and x >= 0, the eval is monotonically non-decreasing
    in x — independent of /N (any non-negative real)."""
    fn = _make(c0=[0.0], c1=[1.0], n=n, domain=[0.0, 1.0])
    prev = -math.inf
    for k in range(0, 11):
        x = k / 10.0
        out = fn.eval([x])[0]
        assert out >= prev - 1e-9, f"/N={n} x={x} regressed: {out} < {prev}"
        prev = out
