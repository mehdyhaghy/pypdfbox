from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSObject
from pypdfbox.pdmodel.common.filespecification import PDFileSpecification
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType2,
    PDFunctionType3,
)
from pypdfbox.pdmodel.common.function import pd_function_type4 as type4


def _array(values: list[float]) -> COSArray:
    arr = COSArray()
    arr.set_float_array(values)
    return arr


def _type2_dict(c0: float, c1: float, domain: list[float] | None = None) -> COSDictionary:
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    raw.set_item("C0", COSArray([COSFloat(c0)]))
    raw.set_item("C1", COSArray([COSFloat(c1)]))
    raw.set_item("N", COSFloat(1.0))
    if domain is not None:
        raw.set_item("Domain", _array(domain))
    return raw


def test_create_fs_returns_none_for_cyclic_indirect_reference() -> None:
    ref = COSObject(12)
    ref.set_object(ref)

    assert PDFileSpecification.create_fs(ref) is None


def test_file_specification_base_methods_are_abstract() -> None:
    spec = PDFileSpecification()

    with pytest.raises(NotImplementedError):
        spec.get_cos_object()
    with pytest.raises(NotImplementedError):
        spec.get_file()
    with pytest.raises(NotImplementedError):
        spec.set_file("example.pdf")


def test_function_constructor_rejects_non_dictionary_or_stream() -> None:
    with pytest.raises(TypeError, match="COSDictionary or COSStream"):
        PDFunction(COSInteger.get(1))


def test_type2_clip_output_stops_when_range_declares_more_outputs() -> None:
    fn = PDFunctionType2(COSDictionary())
    fn.set_range(_array([0.0, 1.0, 0.0, 1.0]))

    assert fn._clip_output_to_range_dimensions([0.25]) == pytest.approx([0.25])


def test_type2_clip_output_accepts_swapped_range_bounds() -> None:
    fn = PDFunctionType2(COSDictionary())
    fn.set_range(_array([1.0, 0.0]))

    assert fn._clip_output_to_range_dimensions([2.0]) == pytest.approx([1.0])


def test_type3_eval_uses_encode_low_for_degenerate_selected_partition() -> None:
    parent = COSDictionary()
    parent.set_int("FunctionType", 3)
    parent.set_item("Domain", _array([0.0, 1.0]))
    parent.set_item("Functions", COSArray([
        _type2_dict(0.0, 1.0, [0.0, 1.0]),
        _type2_dict(10.0, 20.0, [0.0, 1.0]),
    ]))
    parent.set_item("Bounds", _array([1.0]))
    parent.set_item("Encode", _array([0.0, 1.0, 0.25, 0.75]))

    assert PDFunctionType3(parent).eval([1.0]) == pytest.approx([12.5])


def test_type4_pop_bool_returns_boolean_operand() -> None:
    assert type4._pop_bool([True]) is True
