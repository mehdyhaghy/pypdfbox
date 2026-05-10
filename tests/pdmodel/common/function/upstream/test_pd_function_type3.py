"""Ported upstream coverage for ``PDFunctionType3`` (stitching).

Apache PDFBox 3.0 has no dedicated ``PDFunctionType3`` JUnit test class
(only ``TestPDFunctionType4.java`` exists under
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/``).
Stitching is exercised upstream only indirectly through shading / smooth
shading integration tests that require rendering fixtures we have not
ported.

In lieu of a 1:1 class port, this file pins the algorithmic contract of
``PDFunctionType3.eval`` directly against the upstream source so any
divergence in partition selection, encode interpolation, or output
clipping shows up here. The reference iteration is the loop in
``PDFunctionType3.java`` lines ~96-115:

    for (int i=0; i < partitionValuesSize-1; i++) {
        if ( x >= partitionValues[i] &&
                (x < partitionValues[i+1]
                 || (i == partitionValuesSize - 2
                     && Float.compare(x,partitionValues[i+1]) == 0))) {
            function = functionsArray[i];
            PDRange encRange = getEncodeForParameter(i);
            x = interpolate(x, partitionValues[i], partitionValues[i+1],
                            encRange.getMin(), encRange.getMax());
            break;
        }
    }
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunctionType3


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", COSArray([COSFloat(v) for v in c0]))
    raw.set_item("C1", COSArray([COSFloat(v) for v in c1]))
    raw.set_item("N", COSFloat(n))
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain)
    return raw


def _stitch(
    *,
    functions: list[COSDictionary],
    domain: list[float],
    bounds: list[float],
    encode: list[float],
) -> PDFunctionType3:
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    domain_arr = COSArray()
    domain_arr.set_float_array(domain)
    parent.set_item("Domain", domain_arr)
    parent.set_item("Functions", COSArray(list(functions)))
    parent.set_item("Bounds", COSArray([COSFloat(b) for b in bounds]))
    parent.set_item("Encode", COSArray([COSFloat(v) for v in encode]))
    return PDFunctionType3(parent)


# ---------- get_function_type ----------


def test_get_function_type_is_3() -> None:
    """Mirrors ``getFunctionType`` line ~52 (always returns 3)."""
    assert PDFunctionType3().get_function_type() == 3


# ---------- partition selection: x >= partitionValues[i] AND x < next ----------


def test_eval_x_at_lower_domain_picks_first_subfunction() -> None:
    """``x == partitionValues[0]`` (== domain.min) routes to subfunction 0
    because the predicate is ``x >= partitionValues[i]`` for the first
    interval, then ``x < partitionValues[i+1]``."""
    fn = _stitch(
        functions=[_type2([0.1], [0.2]), _type2([0.8], [0.9])],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # Subfunction 0 evaluates to C0 at encoded 0 -> 0.1.
    assert fn.eval([0.0]) == pytest.approx([0.1])


def test_eval_x_at_upper_domain_picks_last_subfunction_via_special_case() -> None:
    """The last partition in the upstream loop is special-cased:
    ``i == partitionValuesSize - 2 && Float.compare(x,partitionValues[i+1]) == 0``
    so ``x == domain.max`` lands in the *last* interval (not the first
    via the relaxed >= predicate)."""
    fn = _stitch(
        functions=[_type2([0.1], [0.2]), _type2([0.8], [0.9])],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # Subfunction 1 at encoded 1 -> C1 = 0.9.
    assert fn.eval([1.0]) == pytest.approx([0.9])


def test_eval_x_equal_to_bound_falls_into_upper_partition() -> None:
    """``x == bounds[i]`` fails ``x < partitionValues[i+1]`` for partition
    ``i`` and matches ``x >= partitionValues[i+1]`` for partition ``i+1``."""
    fn = _stitch(
        functions=[_type2([0.0], [0.25]), _type2([0.75], [1.0])],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # Lands in subfunction 1 at encoded 0 -> 0.75.
    assert fn.eval([0.5]) == pytest.approx([0.75])


# ---------- encode interpolation ----------


def test_eval_interpolates_input_to_encode_range() -> None:
    """Mirrors the ``interpolate(x, partitionValues[i], partitionValues[i+1],
    encRange.getMin(), encRange.getMax())`` step. Halfway through the
    partition produces the encode midpoint."""
    fn = _stitch(
        functions=[_type2([0.0], [1.0])],
        domain=[0.0, 10.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    assert fn.eval([5.0]) == pytest.approx([0.5])


def test_eval_reversed_encode_pair_reverses_subfunction_input() -> None:
    """An encode pair running high->low maps the partition's low end to
    the encode's high end (interpolation handles the reversal)."""
    fn = _stitch(
        functions=[_type2([0.0], [1.0])],
        domain=[0.0, 10.0],
        bounds=[],
        encode=[1.0, 0.0],
    )
    # x=0 -> encoded 1.0 -> subfunction yields C1 = 1.0.
    assert fn.eval([0.0]) == pytest.approx([1.0])


# ---------- input clipping (clipToRange against /Domain) ----------


def test_eval_clips_input_below_domain_min() -> None:
    """Mirrors ``x = clipToRange(x, domain.getMin(), domain.getMax())``
    line ~74 — out-of-range x is pinned to domain bounds before partition
    selection."""
    fn = _stitch(
        functions=[_type2([0.5], [0.7]), _type2([0.0], [0.0])],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    assert fn.eval([-100.0]) == pytest.approx([0.5])


def test_eval_clips_input_above_domain_max() -> None:
    fn = _stitch(
        functions=[_type2([0.0], [0.0]), _type2([0.5], [0.7])],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    assert fn.eval([100.0]) == pytest.approx([0.7])


# ---------- single-function shortcut (functionsArray.length == 1) ----------


def test_eval_single_function_uses_full_domain_to_encode() -> None:
    """Mirrors the ``functionsArray.length == 1`` branch (lines ~80-84):
    ``x = interpolate(x, domain.getMin(), domain.getMax(),
    encRange.getMin(), encRange.getMax())``. Bounds is irrelevant when
    only one function is present."""
    fn = _stitch(
        functions=[_type2([0.0], [1.0])],
        domain=[2.0, 6.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    # x=4 is the midpoint of [2, 6] -> encoded 0.5 -> output 0.5.
    assert fn.eval([4.0]) == pytest.approx([0.5])


# ---------- output clipping (clipToRange against /Range) ----------


def test_eval_clips_subfunction_output_to_range() -> None:
    """Mirrors the trailing ``return clipToRange(functionResult);`` step
    line ~119 — output is clipped against the parent /Range when present."""
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    parent.set_item("Domain", domain)
    parent.set_item("Functions", COSArray([_type2([0.0], [2.0])]))
    parent.set_item("Bounds", COSArray())
    encode = COSArray()
    encode.set_float_array([0.0, 1.0])
    parent.set_item("Encode", encode)
    range_arr = COSArray()
    range_arr.set_float_array([0.0, 1.0])
    parent.set_item("Range", range_arr)
    fn = PDFunctionType3(parent)
    # Subfunction at encoded 1.0 emits 2.0; /Range clips to 1.0.
    assert fn.eval([1.0]) == pytest.approx([1.0])


# ---------- accessors mirror upstream COSArray-returning getters ----------


def test_get_functions_array_returns_raw_cos_array() -> None:
    """Upstream ``getFunctions`` returns a raw COSArray; this port exposes
    that raw view via ``get_functions_array`` (the materialised wrapper
    list lives on ``get_functions``)."""
    fn = _stitch(
        functions=[_type2([0.0], [1.0])],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    arr = fn.get_functions_array()
    assert isinstance(arr, COSArray)
    assert arr.size() == 1


def test_get_bounds_returns_raw_cos_array() -> None:
    """Upstream ``getBounds`` returns the raw COSArray. Mirrors lines
    ~135-140."""
    fn = _stitch(
        functions=[_type2([0.0], [1.0]), _type2([0.0], [1.0])],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    bounds = fn.get_bounds()
    assert isinstance(bounds, COSArray)
    assert bounds.to_float_array() == pytest.approx([0.5])


def test_get_encode_returns_raw_cos_array() -> None:
    """Upstream ``getEncode`` returns the raw COSArray. Mirrors lines
    ~147-153."""
    fn = _stitch(
        functions=[_type2([0.0], [1.0]), _type2([0.0], [1.0])],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 1.0, 0.0],
    )
    encode = fn.get_encode()
    assert isinstance(encode, COSArray)
    assert encode.to_float_array() == pytest.approx([0.0, 1.0, 1.0, 0.0])


def test_get_encode_for_parameter_returns_pair_for_index() -> None:
    """Upstream ``getEncodeForParameter(int n)`` builds a ``PDRange`` from
    ``encodeValues`` at offset ``n``. The Python port returns the (min, max)
    tuple directly (PDRange is not a separate class in this port)."""
    fn = _stitch(
        functions=[_type2([0.0], [1.0]), _type2([0.0], [1.0])],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.1, 0.2, 0.3, 0.4],
    )
    assert fn.get_encode_for_parameter(0) == pytest.approx((0.1, 0.2))
    assert fn.get_encode_for_parameter(1) == pytest.approx((0.3, 0.4))


# ---------- multi-partition routing parity ----------


def test_eval_three_partitions_routes_each_segment_to_its_subfunction() -> None:
    """Stresses the partitionValues construction: domain.min, bounds[0..1],
    domain.max -> 4 entries, 3 partitions."""
    fn = _stitch(
        functions=[
            _type2([0.0], [0.0]),  # constant 0
            _type2([0.5], [0.5]),  # constant 0.5
            _type2([1.0], [1.0]),  # constant 1
        ],
        domain=[0.0, 3.0],
        bounds=[1.0, 2.0],
        encode=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    assert fn.eval([0.5]) == pytest.approx([0.0])
    assert fn.eval([1.5]) == pytest.approx([0.5])
    assert fn.eval([2.5]) == pytest.approx([1.0])
    # x at upper domain hits last partition via the loop's special case.
    assert fn.eval([3.0]) == pytest.approx([1.0])
