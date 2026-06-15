"""Wave 1369 — PDFunctionType3 stitching partition semantics.

The existing Type 3 eval tests in ``test_pd_function_type_3.py`` and
``test_pd_function_type3_eval.py`` cover the structural API surface and
the basic three-subfunction routing. This file rounds out the boundary
semantics that PDF 32000-1 §7.10.4 calls out explicitly:

* The selection predicate is ``[bounds[i-1], bounds[i])`` — left-closed,
  right-open. So x exactly equal to a /Bounds value dispatches to the
  *upper* partition.
* The final partition is closed on both ends — x at /Domain[1] still
  dispatches to the last subfunction.
* Per-partition /Encode maps the subdomain endpoints onto
  ``(encode_min, encode_max)`` — exercise that the encoded input is
  exactly ``encode_min`` at the partition left boundary and exactly
  ``encode_max`` at the right boundary.
* The dispatcher tolerates a sentinel partition with degenerate width
  (e.g. ``bounds = [0.5, 0.5]``) — that partition has zero measure but
  the encode mapping must still produce a finite result.
* Sub-functions of different types (Type 0 sampled and Type 2
  exponential) interleave correctly within a single stitching wrapper.
* Stitching of identity Type 4 PostScript subfunctions still respects
  the partition boundaries.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType3

# ---------- builders ----------


def _type2(
    c0: list[float], c1: list[float], n: float, *, domain: list[float] | None = None
) -> COSDictionary:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    c0_arr = COSArray()
    c0_arr.set_float_array(c0)
    raw.set_item("C0", c0_arr)
    c1_arr = COSArray()
    c1_arr.set_float_array(c1)
    raw.set_item("C1", c1_arr)
    raw.set_item("N", COSFloat(n))
    if domain is None:
        domain = [0.0, 1.0]
    domain_arr = COSArray()
    domain_arr.set_float_array(domain)
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


# ---------- Left-closed / right-open boundary ----------


def test_at_exact_bound_dispatches_to_upper_partition() -> None:
    """x exactly equal to /Bounds[i] must dispatch to subfunction i+1."""
    fn = _stitch(
        # sub0 returns -1, sub1 returns +1; bound at 0.5
        functions=[
            _type2(c0=[-1.0], c1=[-1.0], n=1.0),
            _type2(c0=[1.0], c1=[1.0], n=1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    assert math.isclose(fn.eval([0.4999999])[0], -1.0, rel_tol=1e-9, abs_tol=1e-9)
    # At x exactly equal to bound, dispatches to upper partition.
    assert math.isclose(fn.eval([0.5])[0], 1.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([0.5000001])[0], 1.0, rel_tol=1e-9, abs_tol=1e-9)


def test_domain_left_boundary_dispatches_to_first_partition() -> None:
    """x = /Domain[0] dispatches to partition 0."""
    fn = _stitch(
        functions=[
            _type2(c0=[10.0], c1=[20.0], n=1.0),
            _type2(c0=[30.0], c1=[40.0], n=1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=0 -> partition 0 -> child(0) -> 10
    assert math.isclose(fn.eval([0.0])[0], 10.0, rel_tol=1e-9, abs_tol=1e-9)


def test_domain_right_boundary_dispatches_to_last_partition() -> None:
    """x = /Domain[1] is the right-closed end — dispatches to the last
    partition (not over the cliff)."""
    fn = _stitch(
        functions=[
            _type2(c0=[10.0], c1=[20.0], n=1.0),
            _type2(c0=[30.0], c1=[40.0], n=1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=1 -> partition 1 -> child(1) -> 40
    assert math.isclose(fn.eval([1.0])[0], 40.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Encode end-point semantics ----------


def test_encode_maps_partition_left_endpoint_to_encode_min() -> None:
    """At the left boundary of partition k, the encoded input equals
    encode[2k] — the lower /Encode value for that partition.

    Use child function: y = encode_value (so eval at left boundary
    returns encode[2k]).
    """
    fn = _stitch(
        functions=[
            # sub0: identity x -> x
            _type2(c0=[0.0], c1=[1.0], n=1.0),
            # sub1: identity x -> x but mapped through encode pair (2, 5)
            _type2(c0=[0.0], c1=[1.0], n=1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        # sub0 encode: (0, 1) -- identity; sub1 encode: (2, 5)
        encode=[0.0, 1.0, 2.0, 5.0],
    )
    # sub1 left endpoint x=0.5 -> mapped to enc_min = 2 -> child(2).
    # Type 2 eval does NOT clip its input to /Domain (upstream parity,
    # PDFunctionType2.java; verified via the ShadingFuncProbe oracle, which
    # returns 2.0 for this exact stitch), so child(2) = 0 + 2**1*(1-0) = 2.0.
    assert math.isclose(fn.eval([0.5])[0], 2.0, rel_tol=1e-9, abs_tol=1e-9)


def test_encode_maps_partition_linearly_between_endpoints() -> None:
    """Within partition k, x is linearly mapped from the partition's
    subdomain to the encode pair. For a single-subfunction case with
    /Bounds = []: /Domain = [0, 10], /Encode = [0, 1]; child = identity.
    """
    fn = _stitch(
        functions=[_type2(c0=[0.0], c1=[1.0], n=1.0)],
        domain=[0.0, 10.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    # Linear mapping: x=0 -> 0; x=5 -> 0.5; x=10 -> 1.
    assert math.isclose(fn.eval([0.0])[0], 0.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([2.5])[0], 0.25, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([5.0])[0], 0.5, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([7.5])[0], 0.75, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(fn.eval([10.0])[0], 1.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- Degenerate partition (zero-width) ----------


def test_zero_width_partition_does_not_crash() -> None:
    """A /Bounds = [0.5, 0.5] sequence creates a zero-width middle
    partition. Per the eval division-by-zero guard, the encoded input
    falls back to encode_min for that partition; eval must not crash."""
    fn = _stitch(
        functions=[
            _type2(c0=[1.0], c1=[1.0], n=1.0),
            _type2(c0=[2.0], c1=[2.0], n=1.0),  # zero-width middle
            _type2(c0=[3.0], c1=[3.0], n=1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5, 0.5],
        encode=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    # x exactly 0.5 -> first bound matches (x < 0.5 is false), so try
    # next bound (x < 0.5 again false), so falls into final partition.
    # But we still expect a sensible answer.
    out = fn.eval([0.5])[0]
    # Either middle (2) or final (3) is acceptable per the predicate; we
    # test it's one of those values rather than NaN/crash.
    assert out in (2.0, 3.0), f"degenerate partition produced {out}"


# ---------- Mixed subfunction types ----------


def test_mixed_type2_and_type4_subfunctions() -> None:
    """Type 3 dispatches to subfunctions of any type — Type 2 and Type 4
    can interleave in /Functions."""
    # Build a Type 4 squaring program: input x -> x*x
    type4_stream = COSStream()
    type4_stream.set_int("FunctionType", 4)
    t4_domain = COSArray()
    t4_domain.set_float_array([0.0, 1.0])
    type4_stream.set_item("Domain", t4_domain)
    t4_range = COSArray()
    t4_range.set_float_array([0.0, 1.0])
    type4_stream.set_item("Range", t4_range)
    type4_stream.set_data(b"{ dup mul }")

    fn = _stitch(
        functions=[
            _type2(c0=[0.0], c1=[1.0], n=1.0),  # identity
            type4_stream,  # squaring
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
        range_=[0.0, 1.0],
    )
    # Below bound -> Type 2 identity. x=0.25 maps to sub-domain [0, 0.5]
    # at fraction 0.5, mapped to encode (0, 1) -> 0.5 -> identity -> 0.5.
    assert math.isclose(fn.eval([0.25])[0], 0.5, rel_tol=1e-9, abs_tol=1e-9)
    # Above bound -> Type 4 squaring. x=0.75 maps to sub-domain
    # [0.5, 1.0] at fraction 0.5, mapped to encode (0, 1) -> 0.5 ->
    # squared = 0.25.
    assert math.isclose(fn.eval([0.75])[0], 0.25, rel_tol=1e-9, abs_tol=1e-9)


# ---------- /Bounds longer than n-1 fails ----------


def test_bounds_too_long_with_single_function_ignores_bounds() -> None:
    """Upstream's single-subfunction path dispatches straight to function[0]
    and interpolates over the *whole* /Domain into /Encode pair 0 — /Bounds is
    ignored entirely, even when over-long. Retargeted wave 1523 (oracle:
    FunctionType3FuzzProbe single_with_bound; was a ValueError pre-wave-1523)."""
    fn = _stitch(
        functions=[_type2(c0=[0.0], c1=[1.0], n=1.0)],
        domain=[0.0, 1.0],
        bounds=[0.3, 0.7],  # 2 bounds for 1 function — ignored upstream
        encode=[0.0, 1.0],
    )
    assert fn.eval([0.5]) == pytest.approx([0.5])


# ---------- Empty /Functions fails ----------


def test_empty_functions_raises() -> None:
    """A stitching wrapper with no subfunctions has nothing to dispatch to.
    Upstream builds a zero-length functionsArray, selects partition 0 (the only
    one, [domain_min, domain_max]), then indexes functionsArray[0] ->
    ArrayIndexOutOfBoundsException (-> IndexError here). Retargeted wave 1523
    (oracle: FunctionType3FuzzProbe fns_empty; was ValueError "...Functions...")."""
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    domain_arr = COSArray()
    domain_arr.set_float_array([0.0, 1.0])
    parent.set_item("Domain", domain_arr)
    parent.set_item("Functions", COSArray())  # empty
    parent.set_item("Bounds", COSArray())
    parent.set_item("Encode", COSArray())
    fn = PDFunctionType3(parent)
    with pytest.raises(IndexError):
        fn.eval([0.5])


# ---------- Missing /Domain raises ----------


def test_missing_domain_raises() -> None:
    """Type 3 requires /Domain to know the partition extents."""
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    parent.set_item("Functions", COSArray([_type2(c0=[0.0], c1=[1.0], n=1.0)]))
    parent.set_item("Bounds", COSArray())
    parent.set_item("Encode", COSArray([COSFloat(0.0), COSFloat(1.0)]))
    fn = PDFunctionType3(parent)
    with pytest.raises(ValueError, match="Domain"):
        fn.eval([0.5])


# ---------- /Range clipping at top level ----------


def test_range_clips_subfunction_output() -> None:
    """The stitching wrapper's own /Range clips the subfunction output."""
    fn = _stitch(
        functions=[_type2(c0=[0.0], c1=[100.0], n=1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
        range_=[0.0, 50.0],
    )
    # Without stitch-level /Range, child returns 100. /Range clips to 50.
    assert math.isclose(fn.eval([1.0])[0], 50.0, rel_tol=1e-9, abs_tol=1e-9)


# ---------- Three-partition routing with non-uniform bounds ----------


def test_three_partition_routing_non_uniform_bounds() -> None:
    """Each partition can have a different sub-domain width; the encode
    mapping is per-partition so the scaling differs across partitions."""
    fn = _stitch(
        functions=[
            _type2(c0=[10.0], c1=[20.0], n=1.0),  # sub0: 10 + x*(20-10)
            _type2(c0=[30.0], c1=[40.0], n=1.0),  # sub1: 30 + x*(40-30)
            _type2(c0=[50.0], c1=[60.0], n=1.0),  # sub2: 50 + x*(60-50)
        ],
        domain=[0.0, 10.0],
        bounds=[2.0, 7.0],  # partitions: [0, 2), [2, 7), [7, 10]
        encode=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    # x=1 (partition 0, midway sub-domain) -> mapped to 0.5 -> child = 15.
    assert math.isclose(fn.eval([1.0])[0], 15.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=4.5 (partition 1, midway 2..7) -> mapped to 0.5 -> child = 35.
    assert math.isclose(fn.eval([4.5])[0], 35.0, rel_tol=1e-9, abs_tol=1e-9)
    # x=8.5 (partition 2, midway 7..10) -> mapped to 0.5 -> child = 55.
    assert math.isclose(fn.eval([8.5])[0], 55.0, rel_tol=1e-9, abs_tol=1e-9)
