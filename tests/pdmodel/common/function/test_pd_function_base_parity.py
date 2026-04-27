from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType0,
    PDFunctionType2,
    PDFunctionType3,
    PDFunctionType4,
)


# ---------- get_domain_for_input / get_range_for_input ----------


def _type2_with_domain(domain: list[float]) -> PDFunctionType2:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    domain_arr = COSArray()
    domain_arr.set_float_array(domain)
    raw.set_item("Domain", domain_arr)
    return PDFunctionType2(raw)


def test_get_domain_for_input_returns_first_pair() -> None:
    fn = _type2_with_domain([0.0, 1.0, -2.0, 2.0])
    assert fn.get_domain_for_input(0) == (0.0, 1.0)


def test_get_domain_for_input_returns_second_pair() -> None:
    fn = _type2_with_domain([0.0, 1.0, -2.0, 2.0])
    assert fn.get_domain_for_input(1) == (-2.0, 2.0)


def test_get_range_for_input_aliases_domain() -> None:
    fn = _type2_with_domain([0.25, 0.75])
    # Upstream typo: getRangeForInput actually returns the /Domain pair.
    assert fn.get_range_for_input(0) == fn.get_domain_for_input(0)
    assert fn.get_range_for_input(0) == (0.25, 0.75)


def test_get_domain_for_input_raises_when_out_of_range() -> None:
    fn = _type2_with_domain([0.0, 1.0])
    with pytest.raises(IndexError):
        fn.get_domain_for_input(5)


# ---------- get_range_for_output ----------


def test_get_range_for_output_returns_first_pair() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, 0.0, 0.5, -1.0, 1.0])
    raw.set_item("Range", rng)
    fn = PDFunctionType2(raw)
    assert fn.get_range_for_output(0) == (0.0, 1.0)
    assert fn.get_range_for_output(1) == (0.0, 0.5)
    assert fn.get_range_for_output(2) == (-1.0, 1.0)


def test_get_range_for_output_raises_when_range_absent() -> None:
    fn = PDFunctionType2(COSDictionary())
    with pytest.raises(IndexError):
        fn.get_range_for_output(0)


# ---------- type predicates ----------


def test_is_function_type_2_true_for_type2() -> None:
    fn = PDFunctionType2(COSDictionary())
    assert fn.is_function_type_2() is True
    assert fn.is_function_type_0() is False
    assert fn.is_function_type_3() is False
    assert fn.is_function_type_4() is False


def test_is_function_type_0_true_for_type0() -> None:
    fn = PDFunctionType0(COSStream())
    assert fn.is_function_type_0() is True
    assert fn.is_function_type_2() is False


def test_is_function_type_3_true_for_type3() -> None:
    fn = PDFunctionType3(COSDictionary())
    assert fn.is_function_type_3() is True


def test_is_function_type_4_true_for_type4() -> None:
    fn = PDFunctionType4(COSStream())
    assert fn.is_function_type_4() is True


def test_type_predicates_all_false_for_abstract_base() -> None:
    base = PDFunction()
    assert base.is_function_type_0() is False
    assert base.is_function_type_2() is False
    assert base.is_function_type_3() is False
    assert base.is_function_type_4() is False


# ---------- eval_function alias ----------


def test_eval_function_delegates_to_eval() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", COSArray([COSFloat(0.0)]))
    raw.set_item("C1", COSArray([COSFloat(1.0)]))
    raw.set_item("N", COSFloat(1.0))
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain)
    fn = PDFunctionType2(raw)
    assert fn.eval_function([0.5]) == fn.eval([0.5])
    assert fn.eval_function([0.5]) == pytest.approx([0.5])


# ---------- to_array round trip ----------


def test_to_array_round_trip_floats() -> None:
    arr = PDFunction.to_array([0.0, 0.25, 0.5, 0.75, 1.0])
    assert isinstance(arr, COSArray)
    assert arr.size() == 5
    assert arr.to_float_array() == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])


def test_to_array_round_trip_empty() -> None:
    arr = PDFunction.to_array([])
    assert isinstance(arr, COSArray)
    assert arr.size() == 0


def test_to_array_round_trip_ints_promote_to_float() -> None:
    arr = PDFunction.to_array([1, 2, 3])
    assert arr.size() == 3
    assert arr.to_float_array() == pytest.approx([1.0, 2.0, 3.0])


def test_to_array_results_usable_as_domain() -> None:
    fn = PDFunctionType2(COSDictionary())
    fn.set_domain(PDFunction.to_array([0.0, 1.0, -1.0, 1.0]))
    assert fn.get_number_of_input_parameters() == 2
    assert fn.get_domain_for_input(1) == (-1.0, 1.0)
