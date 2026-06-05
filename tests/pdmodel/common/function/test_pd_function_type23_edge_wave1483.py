"""Wave 1483 — PDFunctionType2/Type3 eval edge-case parity.

Differentially probed against live Apache PDFBox 3.0.7
(``FunctionType23EdgeProbe``); every expected literal below is the exact
value PDFBox's ``PDFunctionType2.eval`` / ``PDFunctionType3.eval`` returns.

Angles covered here that the wave-1369 matrix and the ShadingFuncProbe
battery did not:

Type 2 (exponential):
* **Missing /N → exponent -1, not 1 (BUG FIXED).** Upstream caches
  ``exponent = getCOSObject().getFloat(COSName.N)`` and the single-arg
  ``COSDictionary.getFloat(COSName)`` returns ``-1`` on a missing key. So a
  Type 2 dictionary with no ``/N`` evaluates as ``x**-1`` (= 1/x). pypdfbox
  previously defaulted ``get_n`` to ``1.0``; now mirrors upstream's ``-1.0``.
* ``/N`` = 0 → ``x**0`` = 1 (constant; eval returns C1) including ``0**0``.
* Negative base with fractional ``/N`` → ``Math.pow`` NaN (Python
  ``math.pow`` raises ``ValueError`` → we return ``math.nan``).
* Negative base with integer-valued float ``/N`` (2, 3) → defined real power.
* ``/C0`` longer than ``/C1`` → result sized by ``min(len(C0), len(C1))``.
* Missing ``/C0`` / ``/C1`` → defaults ``[0]`` / ``[1]``.
* ``x`` outside ``[0,1]`` but inside ``/Domain`` → no input clip (Type 2
  does not clip its input — confirmed wave 9946).

Type 3 (stitching):
* Single subfunction, empty ``/Bounds`` → interpolate over the whole domain.
* Single subfunction with reversed ``/Encode`` ``[1 0]``.
* Input exactly AT a ``/Bounds`` value → the HIGHER partition wins
  (upstream's strict ``x < partitionValues[i+1]`` rejects the lower one).
* ``/Domain`` ``[0.2, 0.8]`` edges → input clipped to domain before partition.
* Zero-width subdomain (bound == domain edge) → no divide-by-zero crash.
* Repeated bounds ``[0.5, 0.5]`` → the zero-width middle partition is never
  selected; ``x == 0.5`` lands in the third partition.
* Nested Type3-in-Type3.

These tests pin the literals WITHOUT the oracle (the oracle confirmed them
once; the values are frozen here). A companion @requires_oracle differential
lives in ``oracle/test_function_type23_edge_oracle.py``.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunction


def _floats(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _type2(
    c0: list[float] | None,
    c1: list[float] | None,
    n: float | None,
    domain: list[float],
    range_: list[float] | None = None,
) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", _floats(*domain))
    if c0 is not None:
        d.set_item("C0", _floats(*c0))
    if c1 is not None:
        d.set_item("C1", _floats(*c1))
    if n is not None:
        d.set_item("N", COSFloat(float(n)))
    if range_ is not None:
        d.set_item("Range", _floats(*range_))
    return d


def _type3(
    funcs: list[COSDictionary],
    domain: list[float],
    bounds: list[float],
    encode: list[float],
) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 3)
    d.set_item("Domain", _floats(*domain))
    fa = COSArray()
    for f in funcs:
        fa.add(f)
    d.set_item("Functions", fa)
    ba = COSArray()
    for b in bounds:
        ba.add(COSFloat(float(b)))
    d.set_item("Bounds", ba)
    d.set_item("Encode", _floats(*encode))
    return d


def _close(got: float, want: float) -> bool:
    if math.isnan(want):
        return math.isnan(got)
    return math.isclose(got, want, rel_tol=1e-6, abs_tol=1e-6)


# ---------------- Type 2 ----------------


@pytest.mark.parametrize(
    ("x", "want"),
    [(0.25, 4.0), (0.5, 2.0), (1.0, 1.0), (2.0, 0.5)],
    ids=["quarter", "half", "one", "two"],
)
def test_type2_missing_n_uses_minus_one(x: float, want: float) -> None:
    """Missing /N → exponent -1 → eval(x) = C0 + x**-1*(C1-C0). With C0=0,
    C1=1 that is 1/x. Oracle-confirmed (BUG FIXED in wave 1483)."""
    fn = PDFunction.create(_type2([0], [1], None, [0, 4]))
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize("x", [0.0, 0.5, 1.0], ids=["0", "half", "1"])
def test_type2_n_zero_is_constant_c1(x: float) -> None:
    """/N = 0 → x**0 = 1 (including 0**0) → eval always returns C1."""
    fn = PDFunction.create(_type2([2], [5], 0.0, [0, 1]))
    assert _close(fn.eval([x])[0], 5.0)


@pytest.mark.parametrize(
    ("x", "want"),
    [(-1.0, math.nan), (-0.5, math.nan), (0.5, 0.707107)],
    ids=["neg1", "neghalf", "poshalf"],
)
def test_type2_negative_base_fractional_n_is_nan(x: float, want: float) -> None:
    """Negative base raised to a fractional /N → Math.pow NaN. pypdfbox
    returns math.nan (math.pow raises ValueError on a negative base with a
    non-integer exponent)."""
    fn = PDFunction.create(_type2([0], [1], 0.5, [-2, 2]))
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize(
    ("n", "x", "want"),
    [
        (2.0, -1.0, 1.0),
        (2.0, -0.5, 0.25),
        (2.0, 1.5, 2.25),
        (3.0, -1.0, -1.0),
        (3.0, -0.5, -0.125),
    ],
    ids=["sq-neg1", "sq-neghalf", "sq-1.5", "cube-neg1", "cube-neghalf"],
)
def test_type2_negative_base_integer_n(n: float, x: float, want: float) -> None:
    """A negative base with an integer-valued float /N is a defined real
    power (even N positive, odd N keeps the sign)."""
    fn = PDFunction.create(_type2([0], [1], n, [-2, 2]))
    assert _close(fn.eval([x])[0], want)


def test_type2_c0_longer_than_c1_sized_by_min() -> None:
    """/C0 has 3 entries, /C1 has 2 → result has 2 (min sizing)."""
    fn = PDFunction.create(_type2([0, 0.1, 0.2], [1, 0.9], 1.0, [0, 1]))
    out = fn.eval([0.5])
    assert len(out) == 2
    assert _close(out[0], 0.5)
    assert _close(out[1], 0.5)


@pytest.mark.parametrize(
    ("x", "want"),
    [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)],
    ids=["0", "half", "1"],
)
def test_type2_missing_c0_c1_defaults(x: float, want: float) -> None:
    """No /C0 or /C1 → defaults [0] / [1]; with N=1 that is the identity."""
    fn = PDFunction.create(_type2(None, None, 1.0, [0, 1]))
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize(
    ("x", "want"),
    [(-2.0, -20.0), (-1.0, -10.0), (1.5, 15.0), (2.0, 20.0)],
    ids=["neg2", "neg1", "1.5", "2"],
)
def test_type2_input_outside_unit_but_inside_domain(x: float, want: float) -> None:
    """Type 2 does NOT clip its input to /Domain — an x outside [0,1] but
    inside /Domain [-2,2] feeds straight into the exponent (N=1, C1=10)."""
    fn = PDFunction.create(_type2([0], [10], 1.0, [-2, 2]))
    assert _close(fn.eval([x])[0], want)


# ---------------- Type 3 ----------------


@pytest.mark.parametrize(
    ("x", "want"),
    [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)],
    ids=["0", "half", "1"],
)
def test_type3_single_subfunction_empty_bounds(x: float, want: float) -> None:
    """One subfunction, empty /Bounds → interpolate over the whole domain
    via /Encode [0 1] and dispatch to the single child."""
    fn = PDFunction.create(
        _type3([_type2([0], [1], 1.0, [0, 1])], [0, 1], [], [0, 1])
    )
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize(
    ("x", "want"),
    [(0.0, 1.0), (0.25, 0.75), (1.0, 0.0)],
    ids=["0", "quarter", "1"],
)
def test_type3_single_reversed_encode(x: float, want: float) -> None:
    """One subfunction, reversed /Encode [1 0] → input is flipped before the
    child (C0=0,C1=1,N=1) so eval(x) = 1 - x."""
    fn = PDFunction.create(
        _type3([_type2([0], [1], 1.0, [0, 1])], [0, 1], [], [1, 0])
    )
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize(
    ("x", "want"),
    [
        (0.0, 0.0),
        (0.49999, 0.99998),
        (0.5, 10.0),
        (0.50001, 10.0002),
        (1.0, 20.0),
    ],
    ids=["0", "below-bound", "at-bound", "above-bound", "1"],
)
def test_type3_input_at_bound_selects_higher_partition(
    x: float, want: float
) -> None:
    """Two children, bound 0.5. child0 (C0=0,C1=1) maps [0,0.5)->[0,1).
    child1 (C0=10,C1=20) maps [0.5,1]->[10,20]. Input exactly AT 0.5 lands
    in the HIGHER partition (upstream's strict ``x < bound`` rejects the
    lower one), so eval(0.5) = 10.0 not 1.0."""
    fn = PDFunction.create(
        _type3(
            [_type2([0], [1], 1.0, [0, 1]), _type2([10], [20], 1.0, [0, 1])],
            [0, 1],
            [0.5],
            [0, 1, 0, 1],
        )
    )
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize(
    ("x", "want"),
    [(0.0, 0.0), (0.2, 0.0), (0.5, 1.0), (0.8, 2.0), (1.0, 2.0)],
    ids=["below", "lo-edge", "mid", "hi-edge", "above"],
)
def test_type3_domain_edges_clip_input(x: float, want: float) -> None:
    """/Domain [0.2, 0.8], bound 0.5. Input is clipped to the domain before
    partitioning: x<=0.2 -> child0 at its lower edge (0.0); x>=0.8 -> child1
    at its upper edge (2.0)."""
    fn = PDFunction.create(
        _type3(
            [_type2([0], [1], 1.0, [0, 1]), _type2([1], [2], 1.0, [0, 1])],
            [0.2, 0.8],
            [0.5],
            [0, 1, 0, 1],
        )
    )
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize(
    ("x", "want"),
    [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)],
    ids=["0", "half", "1"],
)
def test_type3_zero_width_first_subdomain(x: float, want: float) -> None:
    """Bound at the domain minimum (0.0) makes the first subdomain zero-width.
    No input ever satisfies ``x < 0``, so child0 is never selected and there
    is no divide-by-zero; every input goes to child1 (C0=0,C1=1) over
    [0,1]."""
    fn = PDFunction.create(
        _type3(
            [_type2([3], [7], 1.0, [0, 1]), _type2([0], [1], 1.0, [0, 1])],
            [0, 1],
            [0.0],
            [0, 1, 0, 1],
        )
    )
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize(
    ("x", "want"),
    [(0.25, 0.5), (0.5, 2.0), (0.75, 2.5)],
    ids=["quarter", "half", "three-quarter"],
)
def test_type3_repeated_bounds_skip_zero_width_middle(
    x: float, want: float
) -> None:
    """Bounds [0.5, 0.5] make the middle partition zero-width. x=0.5 is NOT
    < 0.5 so it skips both child0 and the zero-width child1, landing in
    child2 (C0=2,C1=3) which maps 0.5->2.0. The zero-width middle is never
    selected (no divide-by-zero)."""
    fn = PDFunction.create(
        _type3(
            [
                _type2([0], [1], 1.0, [0, 1]),
                _type2([5], [6], 1.0, [0, 1]),
                _type2([2], [3], 1.0, [0, 1]),
            ],
            [0, 1],
            [0.5, 0.5],
            [0, 1, 0, 1, 0, 1],
        )
    )
    assert _close(fn.eval([x])[0], want)


@pytest.mark.parametrize(
    ("x", "want"),
    [
        (0.25, 2.5),
        (0.5, 0.0),
        (0.6, 0.4),
        (0.75, 1.0),
        (0.9, 0.4),
        (1.0, 0.0),
    ],
    ids=["quarter", "half", "0.6", "three-quarter", "0.9", "1"],
)
def test_type3_nested_in_type3(x: float, want: float) -> None:
    """Outer Type3 (bound 0.5): child0 = a Type2 (C0=2,C1=3) over [0,0.5),
    child1 = an inner Type3 over [0.5,1]. The inner Type3 (bound 0.5) has
    child0 (C0=0,C1=1) and child1 (C0=1,C1=0). Oracle-confirmed values pin
    the full nested dispatch + double encode mapping."""
    inner = _type3(
        [_type2([0], [1], 1.0, [0, 1]), _type2([1], [0], 1.0, [0, 1])],
        [0, 1],
        [0.5],
        [0, 1, 0, 1],
    )
    fn = PDFunction.create(
        _type3(
            [_type2([2], [3], 1.0, [0, 1]), inner],
            [0, 1],
            [0.5],
            [0, 1, 0, 1],
        )
    )
    assert _close(fn.eval([x])[0], want)
