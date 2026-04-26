from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSStream
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType0,
    PDFunctionType2,
    PDFunctionType3,
    PDFunctionType4,
)


# ---------- subtype identification ----------


def test_function_type0_identifies_itself() -> None:
    fn = PDFunctionType0(COSStream())
    assert fn.get_function_type() == 0


def test_function_type2_identifies_itself() -> None:
    fn = PDFunctionType2(COSDictionary())
    assert fn.get_function_type() == 2


def test_function_type3_identifies_itself() -> None:
    fn = PDFunctionType3(COSDictionary())
    assert fn.get_function_type() == 3


def test_function_type4_identifies_itself() -> None:
    fn = PDFunctionType4(COSStream())
    assert fn.get_function_type() == 4


def test_base_function_type_is_abstract() -> None:
    base = PDFunction()
    with pytest.raises(NotImplementedError):
        base.get_function_type()


# ---------- Type 2 round trip ----------


def test_type2_round_trip_c0_c1_n() -> None:
    fn = PDFunctionType2()
    fn.set_c0([0.1, 0.2])
    fn.set_c1([0.9, 0.8])
    fn.set_n(1.0)

    assert fn.get_c0() == pytest.approx([0.1, 0.2])
    assert fn.get_c1() == pytest.approx([0.9, 0.8])
    assert fn.get_n() == pytest.approx(1.0)


def test_type2_defaults_when_keys_absent() -> None:
    fn = PDFunctionType2(COSDictionary())
    # PDF defaults per §7.10.3
    assert fn.get_c0() == [0.0]
    assert fn.get_c1() == [1.0]


# ---------- Type 3 typed children ----------


def test_type3_get_functions_wraps_each_child() -> None:
    child2 = COSDictionary()
    child2.set_int("FunctionType", 2)
    child2.set_item("C0", COSArray([COSFloat(0.0)]))
    child2.set_item("C1", COSArray([COSFloat(1.0)]))
    child2.set_item("N", COSFloat(1.0))

    child3 = COSDictionary()
    child3.set_int("FunctionType", 2)
    child3.set_item("C0", COSArray([COSFloat(1.0)]))
    child3.set_item("C1", COSArray([COSFloat(0.0)]))
    child3.set_item("N", COSFloat(2.0))

    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    parent.set_item("Functions", COSArray([child2, child3]))

    fn3 = PDFunctionType3(parent)
    children = fn3.get_functions()
    assert len(children) == 2
    assert all(isinstance(c, PDFunctionType2) for c in children)
    assert children[0].get_c1() == pytest.approx([1.0])
    assert children[1].get_n() == pytest.approx(2.0)


def test_type3_get_functions_empty_when_key_missing() -> None:
    fn3 = PDFunctionType3(COSDictionary())
    assert fn3.get_functions() == []


# ---------- create() dispatch ----------


def test_create_dispatches_type0() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    assert isinstance(PDFunction.create(raw), PDFunctionType0)


def test_create_dispatches_type2() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    assert isinstance(PDFunction.create(raw), PDFunctionType2)


def test_create_dispatches_type3() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 3)
    assert isinstance(PDFunction.create(raw), PDFunctionType3)


def test_create_dispatches_type4() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    assert isinstance(PDFunction.create(raw), PDFunctionType4)


def test_create_returns_none_for_none_input() -> None:
    assert PDFunction.create(None) is None


def test_create_rejects_unsupported_function_type() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 7)
    with pytest.raises(ValueError):
        PDFunction.create(raw)


def test_create_rejects_non_dictionary_input() -> None:
    with pytest.raises(TypeError):
        PDFunction.create(COSInteger.get(2))


# ---------- domain / range ----------


def test_domain_round_trip_and_input_count() -> None:
    fn = PDFunctionType2()
    domain = COSArray()
    domain.set_float_array([0.0, 1.0, 0.0, 1.0])
    fn.set_domain(domain)
    assert fn.get_domain() is domain
    assert fn.get_number_of_input_parameters() == 2


def test_range_round_trip_and_output_count() -> None:
    fn = PDFunctionType2()
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    fn.set_range(rng)
    assert fn.get_range() is rng
    assert fn.get_number_of_output_parameters() == 3


def test_output_count_zero_when_range_absent() -> None:
    fn = PDFunctionType2()
    assert fn.get_range() is None
    assert fn.get_number_of_output_parameters() == 0


# ---------- Type 0 accessors ----------


def test_type0_accessors() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 0)
    raw.set_item("Size", COSArray([COSInteger.get(4), COSInteger.get(4)]))
    raw.set_int("BitsPerSample", 8)
    raw.set_int("Order", 3)
    raw.set_item("Encode", COSArray([COSFloat(0.0), COSFloat(3.0)]))
    raw.set_item("Decode", COSArray([COSFloat(0.0), COSFloat(1.0)]))

    fn = PDFunctionType0(raw)
    size = fn.get_size()
    assert size is not None and size.size() == 2
    assert fn.get_bits_per_sample() == 8
    assert fn.get_order() == 3
    encode = fn.get_encode()
    assert encode is not None and encode.size() == 2
    decode = fn.get_decode()
    assert decode is not None and decode.size() == 2


def test_type0_order_defaults_to_one() -> None:
    fn = PDFunctionType0(COSStream())
    assert fn.get_order() == 1


# ---------- evaluation ----------


def _make_type2(c0: list[float], c1: list[float], n: float,
                domain: list[float] | None = None,
                rng: list[float] | None = None) -> PDFunctionType2:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", COSArray([COSFloat(v) for v in c0]))
    raw.set_item("C1", COSArray([COSFloat(v) for v in c1]))
    raw.set_item("N", COSFloat(n))
    if domain is not None:
        domain_arr = COSArray()
        domain_arr.set_float_array(domain)
        raw.set_item("Domain", domain_arr)
    if rng is not None:
        range_arr = COSArray()
        range_arr.set_float_array(rng)
        raw.set_item("Range", range_arr)
    return PDFunctionType2(raw)


def test_base_eval_is_abstract() -> None:
    base = PDFunction()
    with pytest.raises(NotImplementedError):
        base.eval([0.0])


def test_type2_eval_at_zero_returns_c0() -> None:
    fn = _make_type2([0.1, 0.2, 0.3], [0.9, 0.8, 0.7], 1.0, domain=[0.0, 1.0])
    assert fn.eval([0.0]) == pytest.approx([0.1, 0.2, 0.3])


def test_type2_eval_at_one_returns_c1() -> None:
    fn = _make_type2([0.1, 0.2, 0.3], [0.9, 0.8, 0.7], 1.0, domain=[0.0, 1.0])
    assert fn.eval([1.0]) == pytest.approx([0.9, 0.8, 0.7])


def test_type2_eval_at_half_with_n1_returns_midpoint() -> None:
    fn = _make_type2([0.0, 0.0], [1.0, 0.5], 1.0, domain=[0.0, 1.0])
    assert fn.eval([0.5]) == pytest.approx([0.5, 0.25])


def test_type2_eval_at_half_with_n2_returns_quarter() -> None:
    # x**N = 0.5**2 = 0.25
    fn = _make_type2([0.0, 1.0], [1.0, 0.0], 2.0, domain=[0.0, 1.0])
    # y[0] = 0 + 0.25*(1-0) = 0.25
    # y[1] = 1 + 0.25*(0-1) = 0.75
    assert fn.eval([0.5]) == pytest.approx([0.25, 0.75])


def test_type2_eval_clips_output_when_range_present() -> None:
    fn = _make_type2(
        [0.0], [2.0], 1.0, domain=[0.0, 1.0], rng=[0.0, 1.0]
    )
    # Without clipping y(1.0) = 2.0; clipped to /Range upper bound 1.0.
    assert fn.eval([1.0]) == pytest.approx([1.0])


def test_clip_input_clamps_below_min() -> None:
    fn = _make_type2([0.0], [1.0], 1.0, domain=[0.2, 0.8])
    assert fn.clip_input([-5.0]) == pytest.approx([0.2])


def test_clip_input_clamps_above_max() -> None:
    fn = _make_type2([0.0], [1.0], 1.0, domain=[0.2, 0.8])
    assert fn.clip_input([5.0]) == pytest.approx([0.8])


def test_get_ranges_for_inputs_pairs_domain() -> None:
    fn = _make_type2([0.0], [1.0], 1.0, domain=[0.0, 1.0, -2.0, 2.0])
    assert fn.get_ranges_for_inputs() == [(0.0, 1.0), (-2.0, 2.0)]


def test_get_ranges_for_outputs_pairs_range() -> None:
    fn = _make_type2([0.0], [1.0], 1.0, rng=[0.0, 1.0, 0.0, 0.5])
    assert fn.get_ranges_for_outputs() == [(0.0, 1.0), (0.0, 0.5)]


def test_type3_eval_routes_to_first_subfunction() -> None:
    # Subfunction 0: C0=[0], C1=[1], N=1 over encoded [0,1]
    sub0 = COSDictionary()
    sub0.set_int("FunctionType", 2)
    sub0.set_item("C0", COSArray([COSFloat(0.0)]))
    sub0.set_item("C1", COSArray([COSFloat(1.0)]))
    sub0.set_item("N", COSFloat(1.0))
    sub0_domain = COSArray()
    sub0_domain.set_float_array([0.0, 1.0])
    sub0.set_item("Domain", sub0_domain)

    # Subfunction 1: C0=[1], C1=[0], N=1 over encoded [0,1]
    sub1 = COSDictionary()
    sub1.set_int("FunctionType", 2)
    sub1.set_item("C0", COSArray([COSFloat(1.0)]))
    sub1.set_item("C1", COSArray([COSFloat(0.0)]))
    sub1.set_item("N", COSFloat(1.0))
    sub1_domain = COSArray()
    sub1_domain.set_float_array([0.0, 1.0])
    sub1.set_item("Domain", sub1_domain)

    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    parent_domain = COSArray()
    parent_domain.set_float_array([0.0, 1.0])
    parent.set_item("Domain", parent_domain)
    parent.set_item("Functions", COSArray([sub0, sub1]))
    parent.set_item("Bounds", COSArray([COSFloat(0.5)]))
    parent.set_item(
        "Encode",
        COSArray([COSFloat(0.0), COSFloat(1.0), COSFloat(0.0), COSFloat(1.0)]),
    )

    fn3 = PDFunctionType3(parent)
    # x = 0.25 falls in sub0's interval [0, 0.5]; mapped to 0.5 in encoded
    # [0,1]; sub0 (linear ramp 0->1) returns 0.5.
    assert fn3.eval([0.25]) == pytest.approx([0.5])
    # x = 0.75 falls in sub1's interval [0.5, 1.0]; mapped to 0.5; sub1
    # (linear ramp 1->0) returns 0.5.
    assert fn3.eval([0.75]) == pytest.approx([0.5])
