"""Hand-written coverage for ``PDFunctionType3`` accessors and stitching eval.

Complements ``test_pd_function_type3_eval.py`` which focuses on numerical
eval behaviour. This module concentrates on the structural API surface:
``get_functions`` / ``set_functions`` / ``get_bounds`` / ``set_bounds`` /
``get_encode`` / ``set_encode`` / ``get_function_type``, plus a handful of
boundary-condition eval cases (single-subfunction degenerate, exact stitch
boundary, three-subfunction routing) that the brief explicitly calls out.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger
from pypdfbox.pdmodel.common.function import PDFunction, PDFunctionType3


# ---------- builders ----------


def _type2(c0: list[float], c1: list[float], n: float) -> COSDictionary:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", COSArray([COSFloat(v) for v in c0]))
    raw.set_item("C1", COSArray([COSFloat(v) for v in c1]))
    raw.set_item("N", COSFloat(n))
    domain_arr = COSArray()
    domain_arr.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain_arr)
    return raw


def _stitch(*, functions: list[COSDictionary],
            domain: list[float],
            bounds: list[float],
            encode: list[float]) -> PDFunctionType3:
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    domain_arr = COSArray()
    domain_arr.set_float_array(domain)
    parent.set_item("Domain", domain_arr)
    parent.set_item("Functions", COSArray(list(functions)))
    parent.set_item("Bounds", COSArray([COSFloat(b) for b in bounds]))
    parent.set_item("Encode", COSArray([COSFloat(v) for v in encode]))
    return PDFunctionType3(parent)


# ---------- type identity ----------


def test_get_function_type_returns_three() -> None:
    fn = PDFunctionType3()
    assert fn.get_function_type() == 3


def test_factory_dispatches_to_type3() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    fn = PDFunction.create(raw)
    assert isinstance(fn, PDFunctionType3)
    assert fn.is_function_type_3()
    assert not fn.is_function_type_2()


# ---------- accessors ----------


def test_get_functions_wraps_each_entry() -> None:
    fn = _stitch(
        functions=[
            _type2([0.0], [1.0], 1.0),
            _type2([1.0], [0.0], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    children = fn.get_functions()
    assert len(children) == 2
    for child in children:
        assert child.get_function_type() == 2


def test_get_functions_skips_non_dict_entries() -> None:
    """Numeric / null /Functions slots are ignored — only dict/stream entries
    yield wrapped subfunctions."""
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    domain_arr = COSArray()
    domain_arr.set_float_array([0.0, 1.0])
    parent.set_item("Domain", domain_arr)
    arr = COSArray()
    arr.add(_type2([0.0], [1.0], 1.0))
    arr.add(COSInteger(7))  # non-dict entry — skipped
    parent.set_item("Functions", arr)
    fn = PDFunctionType3(parent)
    assert len(fn.get_functions()) == 1


def test_get_functions_when_missing_returns_empty_list() -> None:
    fn = PDFunctionType3()
    assert fn.get_functions() == []


def test_get_bounds_when_missing_returns_none() -> None:
    fn = PDFunctionType3()
    assert fn.get_bounds() is None


def test_get_encode_when_missing_returns_none() -> None:
    fn = PDFunctionType3()
    assert fn.get_encode() is None


def test_get_bounds_returns_array() -> None:
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0), _type2([1.0], [0.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[0.4],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    bounds = fn.get_bounds()
    assert bounds is not None
    assert bounds.to_float_array() == pytest.approx([0.4])


def test_get_encode_returns_array() -> None:
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0), _type2([1.0], [0.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 0.5, 0.5, 1.0],
    )
    enc = fn.get_encode()
    assert enc is not None
    assert enc.to_float_array() == pytest.approx([0.0, 0.5, 0.5, 1.0])


# ---------- setters ----------


def test_set_functions_round_trips() -> None:
    fn = PDFunctionType3()
    arr = COSArray([_type2([0.0], [1.0], 1.0)])
    fn.set_functions(arr)
    assert fn.get_cos_object().get_dictionary_object("Functions") is arr


def test_set_functions_with_none_removes_key() -> None:
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    fn.set_functions(None)
    assert fn.get_cos_object().get_dictionary_object("Functions") is None


def test_set_bounds_round_trips() -> None:
    fn = PDFunctionType3()
    arr = COSArray([COSFloat(0.25), COSFloat(0.75)])
    fn.set_bounds(arr)
    assert fn.get_bounds() is arr


def test_set_bounds_with_none_removes_key() -> None:
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0), _type2([1.0], [0.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    fn.set_bounds(None)
    assert fn.get_bounds() is None


def test_set_encode_round_trips() -> None:
    fn = PDFunctionType3()
    arr = COSArray([COSFloat(0.0), COSFloat(1.0)])
    fn.set_encode(arr)
    assert fn.get_encode() is arr


def test_set_encode_with_none_removes_key() -> None:
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    fn.set_encode(None)
    assert fn.get_encode() is None


# ---------- eval boundary cases (per task brief) ----------


def test_eval_single_subfunction_degenerate() -> None:
    """One subfunction, no /Bounds — every input is mapped through a single
    encode pair into the only child."""
    fn = _stitch(
        functions=[_type2([10.0], [20.0], 1.0)],
        domain=[0.0, 4.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    # x=0 -> child(0)=10; x=4 -> child(1)=20; x=2 -> child(0.5)=15.
    assert fn.eval([0.0]) == pytest.approx([10.0])
    assert fn.eval([4.0]) == pytest.approx([20.0])
    assert fn.eval([2.0]) == pytest.approx([15.0])


def test_eval_exact_stitch_boundary_two_subfunctions() -> None:
    """Per spec, x exactly equal to a /Bounds value is dispatched to the
    upper partition (predicate is strict ``x < bounds[i]``)."""
    fn = _stitch(
        functions=[
            _type2([0.0], [0.0], 1.0),  # constant 0
            _type2([1.0], [1.0], 1.0),  # constant 1
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    # Just below bound -> sub0 -> 0.0
    assert fn.eval([0.5 - 1e-9]) == pytest.approx([0.0])
    # Exactly at bound -> sub1 -> 1.0
    assert fn.eval([0.5]) == pytest.approx([1.0])


def test_eval_three_subfunctions_routes_to_each() -> None:
    fn = _stitch(
        functions=[
            _type2([1.0], [1.0], 1.0),  # constant 1
            _type2([2.0], [2.0], 1.0),  # constant 2
            _type2([3.0], [3.0], 1.0),  # constant 3
        ],
        domain=[0.0, 9.0],
        bounds=[3.0, 6.0],
        encode=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    assert fn.eval([1.0]) == pytest.approx([1.0])
    assert fn.eval([4.0]) == pytest.approx([2.0])
    assert fn.eval([7.0]) == pytest.approx([3.0])


def test_eval_uses_get_function_type() -> None:
    """Sanity: the wrapper still self-identifies as Type 3 after eval."""
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    fn.eval([0.5])
    assert fn.get_function_type() == 3


# ---------- get_functions_array (raw COSArray accessor) ----------


def test_get_functions_array_returns_underlying_cos_array() -> None:
    """Mirrors upstream ``getFunctions()`` which returns ``COSArray``."""
    fn = _stitch(
        functions=[
            _type2([0.0], [1.0], 1.0),
            _type2([1.0], [0.0], 1.0),
        ],
        domain=[0.0, 1.0],
        bounds=[0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )
    arr = fn.get_functions_array()
    assert isinstance(arr, COSArray)
    assert arr.size() == 2
    # Same instance round-trips back via the raw accessor.
    assert arr is fn.get_cos_object().get_dictionary_object("Functions")


def test_get_functions_array_returns_none_when_absent() -> None:
    fn = PDFunctionType3()
    assert fn.get_functions_array() is None


def test_get_functions_array_returns_none_when_not_array() -> None:
    """Defensive: malformed /Functions entry (non-array) → None."""
    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    raw.set_int("Functions", 0)  # malformed — not a COSArray
    fn = PDFunctionType3(raw)
    assert fn.get_functions_array() is None


# ---------- get_encode_for_parameter ----------


def test_get_encode_for_parameter_returns_pair() -> None:
    """Each /Encode pair is one entry per subfunction."""
    fn = _stitch(
        functions=[
            _type2([0.0], [1.0], 1.0),
            _type2([0.0], [1.0], 1.0),
            _type2([0.0], [1.0], 1.0),
        ],
        domain=[0.0, 9.0],
        bounds=[3.0, 6.0],
        encode=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
    )
    assert fn.get_encode_for_parameter(0) == pytest.approx((0.1, 0.2))
    assert fn.get_encode_for_parameter(1) == pytest.approx((0.3, 0.4))
    assert fn.get_encode_for_parameter(2) == pytest.approx((0.5, 0.6))


def test_get_encode_for_parameter_out_of_range_returns_none() -> None:
    fn = _stitch(
        functions=[_type2([0.0], [1.0], 1.0)],
        domain=[0.0, 1.0],
        bounds=[],
        encode=[0.0, 1.0],
    )
    assert fn.get_encode_for_parameter(0) == pytest.approx((0.0, 1.0))
    assert fn.get_encode_for_parameter(1) is None
    assert fn.get_encode_for_parameter(99) is None


def test_get_encode_for_parameter_returns_none_when_encode_absent() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    fn = PDFunctionType3(raw)
    assert fn.get_encode_for_parameter(0) is None
