"""Wave 280 coverage for ``PDFunctionType3`` convenience and edge cases."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger
from pypdfbox.pdmodel.common.function import (
    PDFunctionType2,
    PDFunctionType3,
)


def _float_array(values: list[float]) -> COSArray:
    arr = COSArray()
    arr.set_float_array(values)
    return arr


def _type2(
    *,
    c0: list[float] | None = None,
    c1: list[float] | None = None,
    domain: list[float] | None = None,
) -> COSDictionary:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", _float_array(c0 if c0 is not None else [0.0]))
    raw.set_item("C1", _float_array(c1 if c1 is not None else [1.0]))
    raw.set_item("N", COSFloat(1.0))
    raw.set_item("Domain", _float_array(domain if domain is not None else [0.0, 1.0]))
    return raw


def _type3_child() -> COSDictionary:
    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    raw.set_item("Domain", _float_array([0.0, 1.0]))
    raw.set_item("Functions", COSArray([_type2()]))
    raw.set_item("Bounds", COSArray())
    raw.set_item("Encode", _float_array([0.0, 1.0]))
    return raw


def _stitch(
    *,
    functions: list[COSDictionary],
    domain: list[float] | None = None,
    bounds: list[float] | None = None,
    encode: list[float] | None = None,
) -> PDFunctionType3:
    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    if domain is not None:
        raw.set_item("Domain", _float_array(domain))
    raw.set_item("Functions", COSArray(functions))
    if bounds is not None:
        raw.set_item("Bounds", _float_array(bounds))
    if encode is not None:
        raw.set_item("Encode", _float_array(encode))
    return PDFunctionType3(raw)


def test_wave280_missing_and_malformed_accessors_return_empty_defaults() -> None:
    fn = PDFunctionType3()
    assert fn.get_functions() == []
    assert fn.get_functions_array() is None
    assert fn.get_number_of_functions() == 0
    assert fn.get_bounds() is None
    assert fn.get_bounds_values() == []
    assert fn.get_encode() is None
    assert fn.get_encode_values() == []
    assert fn.get_encode_for_parameter(0) is None

    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    raw.set_int("Functions", 7)
    raw.set_int("Bounds", 8)
    raw.set_int("Encode", 9)
    malformed = PDFunctionType3(raw)

    assert malformed.get_functions() == []
    assert malformed.get_functions_array() is None
    assert malformed.get_number_of_functions() == 0
    assert malformed.get_bounds() is None
    assert malformed.get_bounds_values() == []
    assert malformed.get_encode() is None
    assert malformed.get_encode_values() == []


def test_wave280_setters_round_trip_and_clear_raw_cos_arrays() -> None:
    fn = PDFunctionType3()
    functions = COSArray([_type2()])
    bounds = _float_array([0.25, 0.75])
    encode = _float_array([0.0, 1.0, 1.0, 0.0])

    fn.set_functions(functions)
    fn.set_bounds(bounds)
    fn.set_encode(encode)

    assert fn.get_functions_array() is functions
    assert fn.get_cos_object().get_dictionary_object("Functions") is functions
    assert fn.get_bounds() is bounds
    assert fn.get_bounds_values() == pytest.approx([0.25, 0.75])
    assert fn.get_encode() is encode
    assert fn.get_encode_values() == pytest.approx([0.0, 1.0, 1.0, 0.0])

    fn.set_functions(None)
    fn.set_bounds(None)
    fn.set_encode(None)

    assert not fn.get_cos_object().contains_key("Functions")
    assert not fn.get_cos_object().contains_key("Bounds")
    assert not fn.get_cos_object().contains_key("Encode")


def test_wave280_nested_functions_use_factory_dispatch_and_skip_scalars() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    functions = COSArray([_type2(), COSInteger.get(42), _type3_child()])
    raw.set_item("Functions", functions)
    fn = PDFunctionType3(raw)

    children = fn.get_functions()

    assert fn.get_functions_array() is functions
    assert fn.get_number_of_functions() == 3
    assert len(children) == 2
    assert isinstance(children[0], PDFunctionType2)
    assert isinstance(children[1], PDFunctionType3)


def test_wave280_encode_values_and_pairs_are_index_safe() -> None:
    fn = _stitch(
        functions=[_type2(), _type2(), _type2()],
        domain=[0.0, 3.0],
        bounds=[1.0, 2.0],
        encode=[0.1, 0.2, 0.3, 0.4, 0.5],
    )

    assert fn.get_encode_values() == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.5])
    assert fn.get_encode_for_parameter(0) == pytest.approx((0.1, 0.2))
    assert fn.get_encode_for_parameter(1) == pytest.approx((0.3, 0.4))
    assert fn.get_encode_for_parameter(2) is None
    assert fn.get_encode_for_parameter(-1) is None


def test_wave280_eval_raises_when_encode_absent() -> None:
    # Upstream getEncodeForParameter -> PDRange(getEncode(), i).getMin() casts
    # encode[2i] to COSNumber; an absent /Encode dereferences null -> NPE
    # (eval failure). Retargeted wave 1523 (oracle: FunctionType3FuzzProbe
    # single_encode_missing). pypdfbox previously substituted a [0, 1] default.
    fn = _stitch(
        functions=[_type2()],
        domain=[10.0, 20.0],
        bounds=[],
        encode=None,
    )

    with pytest.raises(ValueError, match="Encode"):
        fn.eval([15.0])


def test_wave280_eval_interpolates_parent_domain_into_encode_pairs() -> None:
    fn = _stitch(
        functions=[
            _type2(domain=[0.0, 100.0]),
            _type2(domain=[0.0, 100.0]),
        ],
        domain=[0.0, 4.0],
        bounds=[2.0],
        encode=[10.0, 20.0, 30.0, 50.0],
    )

    assert fn.eval([1.0]) == pytest.approx([15.0])
    assert fn.eval([3.0]) == pytest.approx([40.0])


def test_wave280_eval_over_long_bounds_indexes_past_functions() -> None:
    # 2 functions but 2 bounds (need k-1=1). Upstream does NOT validate the
    # /Bounds length; it builds partition [0, .25, .5, 1] (3 intervals) and for
    # x=0.75 selects interval 2, then indexes functionsArray[2] ->
    # ArrayIndexOutOfBoundsException (-> IndexError here). Retargeted wave 1523
    # (oracle: FunctionType3FuzzProbe bounds_too_many; pypdfbox previously
    # raised a "/Bounds has more partitions" ValueError up front).
    fn = _stitch(
        functions=[_type2(), _type2()],
        domain=[0.0, 1.0],
        bounds=[0.25, 0.5],
        encode=[0.0, 1.0, 0.0, 1.0],
    )

    with pytest.raises(IndexError):
        fn.eval([0.75])
