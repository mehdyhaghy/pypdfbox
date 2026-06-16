"""Wave 1574 — PDFunctionType3 stitching-function fuzz battery.

Hammers the partition-selection and per-subdomain /Encode interpolation logic
of :class:`pypdfbox.pdmodel.common.function.PDFunctionType3` against the exact
PDF 32000-1 §7.10.4 spec formula:

* Subfunction selection by /Bounds. The partition array is
  ``[domain_min, *bounds, domain_max]``; for interval ``i`` the selection
  predicate is ``partition[i] <= x`` and (``x < partition[i+1]`` OR
  ``i`` is the last interval and ``x == partition[i+1]``). So an interior
  bound is left-closed / right-open — x exactly on bounds[i] dispatches to the
  *upper* subfunction. The final interval is closed on both ends.
* /Domain clamping of the input (non-normalising upstream
  ``clipToRange(float,float,float)``): x below Domain[0] clamps up to Domain[0]
  (-> subfunction 0); x at/above Domain[1] clamps down to Domain[1] (-> last
  subfunction).
* Per-subdomain /Encode interpolation: subdomain ``[partition[i],
  partition[i+1]]`` maps linearly onto ``(encode[2i], encode[2i+1])``. Index is
  ``2i`` / ``2i+1`` — NOT ``i``. A reversed encode pair (enc_lo > enc_hi)
  reverses the subdomain.
* Single subfunction (k=1): /Bounds is ignored entirely; the input is
  interpolated across the whole /Domain into /Encode pair 0.
* Two subfunctions with one bound.

Subfunctions are Type 2 exponentials with known closed-form outputs
(``C0 + x**N * (C1 - C0)``; Type 2 does NOT clip its input to /Domain, matching
upstream PDFunctionType2). Outputs are verified against the spec formula,
recomputed in-test, so the assertions are independent of the implementation.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType3

# ---------- builders ----------


def _type2(c0: float, c1: float, n: float = 1.0) -> COSDictionary:
    """Single-output Type 2 exponential: ``y = c0 + x**n * (c1 - c0)``.

    With n=1 this is a plain linear map of the encoded input; the encoded input
    fed in by the stitcher is what we verify against the spec.
    """
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    c0_arr = COSArray()
    c0_arr.set_float_array([c0])
    raw.set_item("C0", c0_arr)
    c1_arr = COSArray()
    c1_arr.set_float_array([c1])
    raw.set_item("C1", c1_arr)
    raw.set_item("N", COSFloat(n))
    domain_arr = COSArray()
    domain_arr.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain_arr)
    return raw


def _stitch(
    *,
    functions: list[COSDictionary | COSStream],
    domain: list[float],
    bounds: list[float],
    encode: list[float],
    range_: list[float] | None = None,
) -> PDFunctionType3:
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    domain_arr = COSArray()
    domain_arr.set_float_array(domain)
    parent.set_item("Domain", domain_arr)
    parent.set_item("Functions", COSArray(list(functions)))
    parent.set_item("Bounds", COSArray([COSFloat(b) for b in bounds]))
    parent.set_item("Encode", COSArray([COSFloat(v) for v in encode]))
    if range_ is not None:
        range_arr = COSArray()
        range_arr.set_float_array(range_)
        parent.set_item("Range", range_arr)
    return PDFunctionType3(parent)


def _spec_eval(
    x: float,
    *,
    domain: list[float],
    bounds: list[float],
    encode: list[float],
    coeffs: list[tuple[float, float, float]],
) -> float:
    """Independent reference implementation of the §7.10.4 spec formula.

    ``coeffs[i] = (c0, c1, n)`` for the Type 2 subfunction i. Returns the
    single output value. Mirrors the selection + interpolation upstream uses.
    """
    d0, d1 = domain
    # non-normalising clamp
    x = d0 if x < d0 else (d1 if x > d1 else x)
    if len(coeffs) == 1:
        enc_lo, enc_hi = encode[0], encode[1]
        ex = _interp(x, d0, d1, enc_lo, enc_hi)
        c0, c1, n = coeffs[0]
        return c0 + ex**n * (c1 - c0)
    partition = [d0, *bounds, d1]
    n_intervals = len(partition) - 1
    for i in range(n_intervals):
        if not (x >= partition[i]):
            continue
        is_last = i == n_intervals - 1
        if x < partition[i + 1] or (is_last and x == partition[i + 1]):
            enc_lo, enc_hi = encode[2 * i], encode[2 * i + 1]
            ex = _interp(x, partition[i], partition[i + 1], enc_lo, enc_hi)
            c0, c1, n = coeffs[i]
            return c0 + ex**n * (c1 - c0)
    raise ValueError("partition not found")


def _interp(x: float, xmin: float, xmax: float, ymin: float, ymax: float) -> float:
    if xmax == xmin:
        return ymin
    return ymin + (x - xmin) * (ymax - ymin) / (xmax - xmin)


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


# ---------- single subfunction (k=1) ----------


@pytest.mark.parametrize(
    "x",
    [-5.0, 0.0, 0.1, 0.5, 0.9, 1.0, 7.0],
    ids=["below", "d0", "x0_1", "mid", "x0_9", "d1", "above"],
)
def test_single_subfunction_ignores_bounds_and_clamps(x: float) -> None:
    """k=1: /Bounds ignored, input clamped to /Domain then interpolated over
    the whole domain into /Encode pair 0."""
    domain = [0.0, 1.0]
    encode = [0.0, 1.0]
    coeffs = [(2.0, 8.0, 1.0)]  # y = 2 + ex*6
    fn = _stitch(
        functions=[_type2(*coeffs[0])],
        domain=domain,
        bounds=[0.3, 0.7],  # deliberately wrong length — must be ignored
        encode=encode,
    )
    expected = _spec_eval(x, domain=domain, bounds=[], encode=encode, coeffs=coeffs)
    assert _close(fn.eval([x])[0], expected)


def test_single_subfunction_encode_scales_domain() -> None:
    """k=1 with /Domain [0,10] and /Encode [0,1]: identity-after-scaling."""
    domain = [0.0, 10.0]
    encode = [0.0, 1.0]
    coeffs = [(0.0, 1.0, 1.0)]  # identity on encoded input
    fn = _stitch(
        functions=[_type2(*coeffs[0])], domain=domain, bounds=[], encode=encode
    )
    for x in (0.0, 2.5, 5.0, 7.5, 10.0):
        expected = _spec_eval(
            x, domain=domain, bounds=[], encode=encode, coeffs=coeffs
        )
        assert _close(fn.eval([x])[0], expected), x


def test_single_subfunction_reversed_encode() -> None:
    """k=1 with reversed /Encode [1,0] flips the domain mapping."""
    domain = [0.0, 1.0]
    encode = [1.0, 0.0]
    coeffs = [(0.0, 1.0, 1.0)]
    fn = _stitch(
        functions=[_type2(*coeffs[0])], domain=domain, bounds=[], encode=encode
    )
    # x=0 -> encoded 1 -> 1; x=1 -> encoded 0 -> 0
    assert _close(fn.eval([0.0])[0], 1.0)
    assert _close(fn.eval([1.0])[0], 0.0)
    assert _close(fn.eval([0.25])[0], 0.75)


# ---------- two subfunctions, one bound ----------


@pytest.mark.parametrize(
    "x",
    [-1.0, 0.0, 0.25, 0.4999999, 0.5, 0.5000001, 0.75, 1.0, 3.0],
    ids=[
        "below",
        "d0",
        "low_mid",
        "just_below_bound",
        "on_bound",
        "just_above_bound",
        "high_mid",
        "d1",
        "above",
    ],
)
def test_two_subfunctions_one_bound(x: float) -> None:
    """Bound at 0.5 splits [0,1] into [0,0.5) and [0.5,1]. On-bound -> upper."""
    domain = [0.0, 1.0]
    bounds = [0.5]
    encode = [0.0, 1.0, 0.0, 1.0]
    coeffs = [(10.0, 20.0, 1.0), (30.0, 40.0, 1.0)]
    fn = _stitch(
        functions=[_type2(*coeffs[0]), _type2(*coeffs[1])],
        domain=domain,
        bounds=bounds,
        encode=encode,
    )
    expected = _spec_eval(
        x, domain=domain, bounds=bounds, encode=encode, coeffs=coeffs
    )
    assert _close(fn.eval([x])[0], expected)


def test_on_bound_dispatches_to_upper_subfunction() -> None:
    """x exactly equal to bounds[0] selects subfunction 1 (right of bound)."""
    coeffs = [(-1.0, -1.0, 1.0), (1.0, 1.0, 1.0)]
    fn = _stitch(
        functions=[_type2(*coeffs[0]), _type2(*coeffs[1])],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    assert _close(fn.eval([0.4999999])[0], -1.0)
    assert _close(fn.eval([0.5])[0], 1.0)


def test_below_domain_min_uses_subfunction_zero() -> None:
    """x < Domain[0] clamps up to Domain[0] -> subfunction 0 at its left end."""
    domain = [0.0, 1.0]
    bounds = [0.5]
    encode = [0.0, 1.0, 0.0, 1.0]
    coeffs = [(10.0, 20.0, 1.0), (30.0, 40.0, 1.0)]
    fn = _stitch(
        functions=[_type2(*coeffs[0]), _type2(*coeffs[1])],
        domain=domain,
        bounds=bounds,
        encode=encode,
    )
    # clamp to 0 -> sub0 encoded 0 -> 10
    assert _close(fn.eval([-99.0])[0], 10.0)


def test_at_or_above_domain_max_uses_last_subfunction() -> None:
    """x >= Domain[1] clamps to Domain[1] -> last subfunction at its right end."""
    domain = [0.0, 1.0]
    bounds = [0.5]
    encode = [0.0, 1.0, 0.0, 1.0]
    coeffs = [(10.0, 20.0, 1.0), (30.0, 40.0, 1.0)]
    fn = _stitch(
        functions=[_type2(*coeffs[0]), _type2(*coeffs[1])],
        domain=domain,
        bounds=bounds,
        encode=encode,
    )
    # clamp to 1 -> last interval [0.5,1], encoded 1 -> sub1 = 40
    assert _close(fn.eval([99.0])[0], 40.0)
    assert _close(fn.eval([1.0])[0], 40.0)


# ---------- per-subdomain /Encode is indexed 2i / 2i+1 ----------


def test_encode_index_is_2i_not_i() -> None:
    """The encode pair for subfunction i is encode[2i],encode[2i+1]. A flat
    [0,1, 2,5, 0,1] means sub1 encodes onto (2,5). At sub1's left endpoint the
    encoded input is exactly 2."""
    domain = [0.0, 1.0]
    bounds = [0.5]
    encode = [0.0, 1.0, 2.0, 5.0]
    coeffs = [(0.0, 1.0, 1.0), (0.0, 1.0, 1.0)]  # identity on encoded input
    fn = _stitch(
        functions=[_type2(*coeffs[0]), _type2(*coeffs[1])],
        domain=domain,
        bounds=bounds,
        encode=encode,
    )
    # sub1 left endpoint x=0.5 -> encoded enc_lo = 2 -> identity -> 2.0
    assert _close(fn.eval([0.5])[0], 2.0)
    # sub1 right endpoint x=1.0 -> encoded enc_hi = 5 -> 5.0
    assert _close(fn.eval([1.0])[0], 5.0)
    # midpoint of sub1 x=0.75 -> encoded 3.5
    assert _close(fn.eval([0.75])[0], 3.5)


def test_encode_reverses_a_subdomain() -> None:
    """A reversed encode pair (enc_lo > enc_hi) for one subfunction maps its
    left endpoint to the higher value and its right endpoint to the lower."""
    domain = [0.0, 1.0]
    bounds = [0.5]
    # sub0 normal (0->0, .5->1); sub1 reversed (.5->1, 1->0)
    encode = [0.0, 1.0, 1.0, 0.0]
    coeffs = [(0.0, 1.0, 1.0), (0.0, 1.0, 1.0)]
    fn = _stitch(
        functions=[_type2(*coeffs[0]), _type2(*coeffs[1])],
        domain=domain,
        bounds=bounds,
        encode=encode,
    )
    # sub1 left (x=0.5) -> encoded 1 -> 1.0; sub1 right (x=1) -> encoded 0 -> 0.0
    assert _close(fn.eval([0.5])[0], 1.0)
    assert _close(fn.eval([1.0])[0], 0.0)
    assert _close(fn.eval([0.75])[0], 0.5)


# ---------- three subfunctions, non-uniform bounds ----------


@pytest.mark.parametrize(
    "x",
    [0.0, 1.0, 2.0, 4.5, 6.9999, 7.0, 8.5, 10.0],
    ids=["d0", "p0mid", "on_b0", "p1mid", "just_below_b1", "on_b1", "p2mid", "d1"],
)
def test_three_subfunctions_non_uniform_bounds(x: float) -> None:
    """Bounds [2,7] over Domain [0,10]: intervals [0,2),[2,7),[7,10].
    Each interval encodes its own subdomain onto (0,1) so the per-partition
    scaling differs."""
    domain = [0.0, 10.0]
    bounds = [2.0, 7.0]
    encode = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    coeffs = [(10.0, 20.0, 1.0), (30.0, 40.0, 1.0), (50.0, 60.0, 1.0)]
    fn = _stitch(
        functions=[_type2(*c) for c in coeffs],
        domain=domain,
        bounds=bounds,
        encode=encode,
    )
    expected = _spec_eval(
        x, domain=domain, bounds=bounds, encode=encode, coeffs=coeffs
    )
    assert _close(fn.eval([x])[0], expected)


def test_three_subfunctions_distinct_encode_ranges() -> None:
    """Different encode ranges per partition combine the subdomain scaling and
    the encode scaling — verify against the spec formula for several inputs."""
    domain = [0.0, 9.0]
    bounds = [3.0, 6.0]  # [0,3),[3,6),[6,9]
    encode = [0.0, 2.0, -1.0, 1.0, 10.0, 20.0]
    coeffs = [(0.0, 1.0, 1.0), (0.0, 1.0, 2.0), (0.0, 1.0, 1.0)]
    fn = _stitch(
        functions=[_type2(*c) for c in coeffs],
        domain=domain,
        bounds=bounds,
        encode=encode,
    )
    for x in (0.0, 1.5, 3.0, 4.5, 6.0, 7.5, 9.0):
        expected = _spec_eval(
            x, domain=domain, bounds=bounds, encode=encode, coeffs=coeffs
        )
        assert _close(fn.eval([x])[0], expected), x


# ---------- /Domain clamping with non-[0,1] domain ----------


def test_domain_clamping_non_unit_domain() -> None:
    """Domain [-2, 4]: x below -2 clamps to -2, x above 4 clamps to 4."""
    domain = [-2.0, 4.0]
    bounds = [1.0]
    encode = [0.0, 1.0, 0.0, 1.0]
    coeffs = [(0.0, 100.0, 1.0), (200.0, 300.0, 1.0)]
    fn = _stitch(
        functions=[_type2(*coeffs[0]), _type2(*coeffs[1])],
        domain=domain,
        bounds=bounds,
        encode=encode,
    )
    for x in (-100.0, -2.0, -0.5, 0.9999, 1.0, 2.5, 4.0, 50.0):
        expected = _spec_eval(
            x, domain=domain, bounds=bounds, encode=encode, coeffs=coeffs
        )
        assert _close(fn.eval([x])[0], expected), x


# ---------- nonlinear subfunction through stitcher ----------


def test_nonlinear_subfunction_encoded_input() -> None:
    """A Type 2 with N=2 squares its (encoded) input. Verify the stitcher feeds
    the correctly-encoded input by comparing to the spec formula."""
    domain = [0.0, 1.0]
    bounds = [0.5]
    encode = [0.0, 1.0, 0.0, 1.0]
    coeffs = [(0.0, 1.0, 2.0), (0.0, 1.0, 2.0)]  # y = ex**2
    fn = _stitch(
        functions=[_type2(*coeffs[0]), _type2(*coeffs[1])],
        domain=domain,
        bounds=bounds,
        encode=encode,
        range_=[0.0, 1.0],
    )
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        expected = _spec_eval(
            x, domain=domain, bounds=bounds, encode=encode, coeffs=coeffs
        )
        assert _close(fn.eval([x])[0], expected), x


# ---------- /Range clipping at the stitcher level ----------


def test_range_clips_output() -> None:
    """The stitcher's own /Range clamps the subfunction output."""
    fn = _stitch(
        functions=[_type2(0.0, 100.0, 1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
        range_=[0.0, 50.0],
    )
    assert _close(fn.eval([1.0])[0], 50.0)  # child 100 clipped to 50
    assert _close(fn.eval([0.0])[0], 0.0)


# ---------- empty input raises ----------


def test_empty_input_raises() -> None:
    fn = _stitch(
        functions=[_type2(0.0, 1.0, 1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    with pytest.raises(IndexError):
        fn.eval([])
