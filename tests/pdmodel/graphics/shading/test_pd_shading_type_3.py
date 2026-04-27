"""Additional parity tests for the radial-gradient (Type 3) shading
wrapper, complementing ``test_pd_shading_type3_parity.py`` with coverage
for the new array-form ``/Function`` accessors and the
``get_functions_array`` helper added in this round.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import (
    PDFunctionType2,
)
from pypdfbox.pdmodel.graphics.shading import PDShadingType3


def _make_function_type2_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    domain = COSArray()
    for v in (0.0, 1.0):
        domain.add(COSFloat(v))
    d.set_item("Domain", domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    d.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    d.set_item("C1", c1)
    d.set_int("N", 1)
    return d


def test_get_functions_array_empty_when_function_absent():
    assert PDShadingType3().get_functions_array() == []


def test_get_functions_array_single_function():
    s = PDShadingType3()
    s.set_function(_make_function_type2_dict())
    arr = s.get_functions_array()
    assert len(arr) == 1
    assert isinstance(arr[0], PDFunctionType2)


def test_get_function_returns_cos_array_when_function_is_array():
    s = PDShadingType3()
    arr = COSArray()
    arr.add(_make_function_type2_dict())
    arr.add(_make_function_type2_dict())
    arr.add(_make_function_type2_dict())
    s.set_function(arr)
    got = s.get_function()
    assert got is arr


def test_get_functions_array_unpacks_array_function():
    s = PDShadingType3()
    arr = COSArray()
    arr.add(_make_function_type2_dict())
    arr.add(_make_function_type2_dict())
    s.set_function(arr)
    unwrapped = s.get_functions_array()
    assert len(unwrapped) == 2
    assert all(isinstance(f, PDFunctionType2) for f in unwrapped)
