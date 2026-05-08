from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSStream
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType0,
    PDFunctionType2,
    PDFunctionType4,
    PDFunctionTypeIdentity,
)


def _array(values: list[float]) -> COSArray:
    arr = COSArray()
    arr.set_float_array(values)
    return arr


def test_create_missing_function_type_reports_unsupported_minus_one() -> None:
    with pytest.raises(ValueError, match=r"Unsupported /FunctionType value: -1"):
        PDFunction.create(COSDictionary())


def test_create_rejects_non_identity_name() -> None:
    with pytest.raises(TypeError, match="COSDictionary or COSStream"):
        PDFunction.create(COSName.get_pdf_name("NotIdentity"))


def test_create_dispatches_stream_type0_and_marks_type_function() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", PDFunction.FUNCTION_TYPE_SAMPLED)
    fn = PDFunction.create(raw)

    assert isinstance(fn, PDFunctionType0)
    assert fn.get_cos_object() is raw
    assert fn.is_stream_backed() is True
    assert raw.get_name("Type") == "Function"


def test_create_dispatches_stream_type4_and_marks_type_function() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", PDFunction.FUNCTION_TYPE_POSTSCRIPT)
    fn = PDFunction.create(raw)

    assert isinstance(fn, PDFunctionType4)
    assert fn.get_cos_object() is raw
    assert fn.is_stream_backed() is True
    assert raw.get_name("Type") == "Function"


def test_create_dispatches_dictionary_type2_without_replacing_cos_object() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", PDFunction.FUNCTION_TYPE_EXPONENTIAL)
    raw.set_item("Domain", _array([0.0, 1.0]))

    fn = PDFunction.create(raw)

    assert isinstance(fn, PDFunctionType2)
    assert fn.get_cos_object() is raw
    assert fn.get_domain_for_input(0) == (0.0, 1.0)


def test_domain_and_range_set_none_remove_existing_entries() -> None:
    fn = PDFunctionType2()
    fn.set_domain(_array([0.0, 1.0]))
    fn.set_range(_array([-1.0, 1.0]))

    fn.set_domain(None)
    fn.set_range(None)

    assert fn.get_cos_object().get_dictionary_object("Domain") is None
    assert fn.get_cos_object().get_dictionary_object("Range") is None
    assert fn.get_number_of_input_parameters() == 0
    assert fn.get_number_of_output_parameters() == 0


def test_malformed_domain_and_range_names_are_ignored_by_accessors() -> None:
    raw = COSDictionary()
    raw.set_item("Domain", COSName.get_pdf_name("BadDomain"))
    raw.set_item("Range", COSName.get_pdf_name("BadRange"))
    fn = PDFunctionType2(raw)

    assert fn.get_domain() is None
    assert fn.get_range() is None
    assert fn.get_ranges_for_inputs() == []
    assert fn.get_ranges_for_outputs() == []


def test_odd_domain_and_range_lengths_truncate_to_complete_pairs() -> None:
    raw = COSDictionary()
    raw.set_item("Domain", _array([0.0, 1.0, 9.0]))
    raw.set_item("Range", _array([-1.0, 1.0, 99.0]))
    fn = PDFunctionType2(raw)

    assert fn.get_number_of_input_parameters() == 1
    assert fn.get_number_of_output_parameters() == 1
    assert fn.get_ranges_for_inputs() == [(0.0, 1.0)]
    assert fn.get_ranges_for_outputs() == [(-1.0, 1.0)]


def test_get_domain_for_input_rejects_negative_index() -> None:
    fn = PDFunctionType2()
    fn.set_domain(_array([0.0, 1.0]))

    with pytest.raises(IndexError, match="input dimension -1 out of range"):
        fn.get_domain_for_input(-1)


def test_get_range_for_output_rejects_negative_index() -> None:
    fn = PDFunctionType2()
    fn.set_range(_array([0.0, 1.0]))

    with pytest.raises(IndexError, match="output dimension -1 out of range"):
        fn.get_range_for_output(-1)


def test_clip_input_and_output_swapped_bounds_are_normalized() -> None:
    fn = PDFunctionType2()
    fn.set_domain(_array([10.0, 0.0]))
    fn.set_range(_array([2.0, -2.0]))

    assert fn.clip_input([-5.0, 42.0]) == [0.0, 42.0]
    assert fn.clip_output([5.0, 42.0]) == [2.0, 42.0]


def test_clip_output_without_range_returns_copy() -> None:
    fn = PDFunctionType2()
    values = [1.0, 2.0]

    clipped = fn.clip_output(values)

    assert clipped == values
    assert clipped is not values


def test_eval_function_on_abstract_base_preserves_not_implemented_message() -> None:
    with pytest.raises(NotImplementedError, match=r"eval\(\) is not implemented"):
        PDFunction().eval_function([0.0])


def test_base_get_function_type_not_implemented_message_names_method() -> None:
    with pytest.raises(NotImplementedError, match="get_function_type"):
        PDFunction().get_function_type()


def test_identity_eval_returns_defensive_copy() -> None:
    values = [0.1, 0.2]
    result = PDFunctionTypeIdentity().eval(values)

    assert result == values
    assert result is not values


def test_identity_predicates_remain_false_because_type_is_undefined() -> None:
    fn = PDFunctionTypeIdentity()

    assert fn.is_function_type_0() is False
    assert fn.is_function_type_2() is False
    assert fn.is_function_type_3() is False
    assert fn.is_function_type_4() is False


def test_to_array_accepts_generator_and_stores_cos_float_values() -> None:
    arr = PDFunction.to_array(float(i) / 10.0 for i in range(3))

    assert arr.to_float_array() == pytest.approx([0.0, 0.1, 0.2])
    assert all(isinstance(arr.get(i), COSFloat) for i in range(arr.size()))


def test_function_type_float_value_is_truncated_by_factory_dispatch() -> None:
    raw = COSDictionary()
    raw.set_item("FunctionType", COSFloat(2.9))

    assert isinstance(PDFunction.create(raw), PDFunctionType2)


def test_function_type_integer_value_is_used_by_factory_dispatch() -> None:
    raw = COSDictionary()
    raw.set_item("FunctionType", COSInteger.get(2))

    assert isinstance(PDFunction.create(raw), PDFunctionType2)
