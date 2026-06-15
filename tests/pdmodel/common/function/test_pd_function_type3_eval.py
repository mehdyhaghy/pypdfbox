"""Hand-written eval coverage for ``PDFunctionType3`` (stitching).

Builds Type 3 functions out of two Type 2 (exponential interpolation) child
functions and exercises the partition selection / encode interpolation /
output-clip behaviour mandated by PDF 32000-1 §7.10.4 and mirrored from
``org.apache.pdfbox.pdmodel.common.function.PDFunctionType3.eval``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunctionType3


def _type2(c0: list[float], c1: list[float], n: float,
           domain: list[float] = (0.0, 1.0)) -> COSDictionary:
    """Return a /FunctionType 2 child dictionary (raw, unwrapped)."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", COSArray([COSFloat(v) for v in c0]))
    raw.set_item("C1", COSArray([COSFloat(v) for v in c1]))
    raw.set_item("N", COSFloat(n))
    domain_arr = COSArray()
    domain_arr.set_float_array(list(domain))
    raw.set_item("Domain", domain_arr)
    return raw


def _stitch(*, functions: list[COSDictionary],
            domain: list[float],
            bounds: list[float],
            encode: list[float],
            output_range: list[float] | None = None) -> PDFunctionType3:
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    domain_arr = COSArray()
    domain_arr.set_float_array(domain)
    parent.set_item("Domain", domain_arr)
    parent.set_item("Functions", COSArray(list(functions)))
    parent.set_item("Bounds", COSArray([COSFloat(b) for b in bounds]))
    parent.set_item("Encode", COSArray([COSFloat(v) for v in encode]))
    if output_range is not None:
        range_arr = COSArray()
        range_arr.set_float_array(output_range)
        parent.set_item("Range", range_arr)
    return PDFunctionType3(parent)


# ---------- two-function partition routing ----------


def test_eval_at_lower_domain_routes_to_first_subfunction() -> None:
    # sub0: linear 0 -> 1; sub1: linear 1 -> 0 across encoded [0, 1].
    fn = _stitch(
        functions=[
            _type2([0.0], [1.0], 1.0),
            _type2([1.0], [0.0], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=0 sits at the bottom of sub0's interval; encoded x=0 -> sub0(0)=0.
    assert fn.eval([0.0]) == pytest.approx([0.0])


def test_eval_at_upper_domain_routes_to_last_subfunction() -> None:
    fn = _stitch(
        functions=[
            _type2([0.0], [1.0], 1.0),
            _type2([1.0], [0.0], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=1 sits at the top of sub1's interval; encoded x=1 -> sub1(1)=0.
    assert fn.eval([1.0]) == pytest.approx([0.0])


def test_eval_at_bound_value_routes_to_upper_segment() -> None:
    """Per upstream: x exactly equal to a /Bounds value falls into the
    *upper* partition (the predicate is ``x < bounds[i]``)."""
    fn = _stitch(
        functions=[
            _type2([0.0], [0.25], 1.0),  # range 0..0.25
            _type2([0.75], [1.0], 1.0),  # range 0.75..1.0 — disjoint from sub0
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=0.5 is the bound; lands in sub1, encoded x=0 -> sub1(0)=0.75.
    assert fn.eval([0.5]) == pytest.approx([0.75])


def test_eval_midpoint_of_first_partition() -> None:
    fn = _stitch(
        functions=[
            _type2([0.0], [1.0], 1.0),
            _type2([1.0], [0.0], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=0.25 -> sub0 partition [0, 0.5] -> encoded 0.5 -> sub0(0.5)=0.5.
    assert fn.eval([0.25]) == pytest.approx([0.5])


def test_eval_midpoint_of_last_partition() -> None:
    fn = _stitch(
        functions=[
            _type2([0.0], [1.0], 1.0),
            _type2([1.0], [0.0], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=0.75 -> sub1 partition [0.5, 1.0] -> encoded 0.5 -> sub1(0.5)=0.5.
    assert fn.eval([0.75]) == pytest.approx([0.5])


# ---------- input clipping at /Domain edges ----------


def test_eval_clips_input_below_domain() -> None:
    fn = _stitch(
        functions=[
            _type2([0.2], [0.3], 1.0),
            _type2([0.6], [0.9], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=-2 clips to 0 -> sub0(0)=C0=0.2.
    assert fn.eval([-2.0]) == pytest.approx([0.2])


def test_eval_clips_input_above_domain() -> None:
    fn = _stitch(
        functions=[
            _type2([0.2], [0.3], 1.0),
            _type2([0.6], [0.9], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=99 clips to 1 -> sub1, encoded 1 -> sub1(1)=C1=0.9.
    assert fn.eval([99.0]) == pytest.approx([0.9])


# ---------- non-trivial /Encode (reverses subfunction input) ----------


def test_eval_encode_reverses_subfunction_input() -> None:
    """If the per-partition /Encode pair runs high->low, the subfunction
    sees the *reversed* normalized input."""
    fn = _stitch(
        functions=[
            _type2([0.0], [1.0], 1.0),  # linear 0 -> 1
            _type2([0.0], [1.0], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        # Reverse sub0's encode: low end of partition maps to encoded 1.0.
        encode=[1.0, 0.0, 0.0, 1.0],
    )
    # x=0 in sub0 partition [0, 0.5]; reversed encode -> encoded 1.0 -> sub0(1)=1.
    assert fn.eval([0.0]) == pytest.approx([1.0])
    # x=0.5 (bound -> upper partition); sub1 with normal encode -> encoded 0 -> 0.
    assert fn.eval([0.5]) == pytest.approx([0.0])


# ---------- multi-output dispatch ----------


def test_eval_propagates_multi_output_subfunction() -> None:
    """Stitching is 1-input but children may emit n outputs — they must
    flow through unchanged (modulo /Range clipping)."""
    fn = _stitch(
        functions=[
            _type2([0.0, 0.0, 0.0], [1.0, 0.5, 0.25], 1.0),
            _type2([1.0, 0.5, 0.25], [0.0, 0.0, 0.0], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # x=0.25 -> sub0, encoded 0.5 -> [0.5, 0.25, 0.125].
    assert fn.eval([0.25]) == pytest.approx([0.5, 0.25, 0.125])


# ---------- /Range output clipping ----------


def test_eval_clips_output_to_range() -> None:
    fn = _stitch(
        functions=[
            _type2([0.0], [2.0], 1.0),  # would emit 0..2 across encoded 0..1
            _type2([0.0], [2.0], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
        output_range=[0.0, 1.0],
    )
    # sub0(1.0) would be 2.0; clipped to /Range upper bound 1.0.
    assert fn.eval([0.5 - 1e-9]) == pytest.approx([1.0])


# ---------- single-function stitching (degenerate) ----------


def test_eval_single_function_uses_full_domain_for_encode() -> None:
    """A 1-function stitching dispatches every x to the only child, mapping
    /Domain straight to that child's encoded interval."""
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    assert fn.eval([0.0]) == pytest.approx([0.0])
    assert fn.eval([0.5]) == pytest.approx([0.5])
    assert fn.eval([1.0]) == pytest.approx([1.0])


# ---------- three-partition routing ----------


def test_eval_three_partitions_routes_each_segment() -> None:
    fn = _stitch(
        functions=[
            _type2([0.0], [0.0], 1.0),  # constant 0
            _type2([0.5], [0.5], 1.0),  # constant 0.5
            _type2([1.0], [1.0], 1.0),  # constant 1
        ],
        domain=[0.0, 3.0],
        bounds=[1.0, 2.0],
        encode=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    assert fn.eval([0.5]) == pytest.approx([0.0])
    assert fn.eval([1.5]) == pytest.approx([0.5])
    assert fn.eval([2.5]) == pytest.approx([1.0])
    # Bounds go to upper segments.
    assert fn.eval([1.0]) == pytest.approx([0.5])
    assert fn.eval([2.0]) == pytest.approx([1.0])


# ---------- error paths ----------


def test_eval_without_functions_raises() -> None:
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    domain_arr = COSArray()
    domain_arr.set_float_array([0.0, 1.0])
    parent.set_item("Domain", domain_arr)
    fn = PDFunctionType3(parent)
    with pytest.raises(ValueError):
        fn.eval([0.5])


def test_eval_without_domain_raises() -> None:
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    # Wipe /Domain post-construction to trigger the missing-domain branch.
    fn.get_cos_object().remove_item("Domain")
    with pytest.raises(ValueError):
        fn.eval([0.5])


def test_eval_with_empty_input_raises() -> None:
    # Upstream PDFunctionType3.eval reads input[0] directly; an empty array
    # raises ArrayIndexOutOfBoundsException (-> IndexError here). Retargeted
    # wave 1523 to mirror that (was ValueError pre-wave-1523).
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    with pytest.raises(IndexError):
        fn.eval([])
