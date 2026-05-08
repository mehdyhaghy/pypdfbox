from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunctionType2
from pypdfbox.pdmodel.graphics.shading import PDShadingType3


def _make_function_type2_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    d.set_item("Domain", domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    d.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    d.set_item("C1", c1)
    d.set_int("N", 1)
    return d


def test_type3_set_function_accepts_per_component_iterable() -> None:
    shading = PDShadingType3()
    f1 = PDFunctionType2(_make_function_type2_dict())
    f2 = PDFunctionType2(_make_function_type2_dict())

    shading.set_function([f1, f2])

    raw = shading.get_cos_object().get_dictionary_object("Function")
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    assert raw.get_object(0) is f1.get_cos_object()
    assert raw.get_object(1) is f2.get_cos_object()
    assert shading.get_function() is raw
    assert all(
        isinstance(function, PDFunctionType2)
        for function in shading.get_functions_array()
    )


def test_type3_set_function_rejects_bad_iterable_entry() -> None:
    shading = PDShadingType3()

    with pytest.raises(TypeError, match="iterable entries"):
        shading.set_function([object()])
