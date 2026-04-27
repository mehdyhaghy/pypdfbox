"""Upstream parity tests for ``PDShadingType1``.

Apache PDFBox 3.0.x ships no dedicated ``PDShadingType1Test``; the upstream
project exercises Type 1 shading only indirectly through PDF rendering
parity fixtures. The hand-written tests in
``tests/pdmodel/graphics/shading/test_pd_shading_type_1.py`` cover the COS
metadata round-trip surface that does have direct upstream-API parity.
The tests below mirror the structural assertions an upstream-style unit
test would perform: shading-type identity, default ``/Domain`` shape, and
``/Function`` factory dispatch.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunctionType2
from pypdfbox.pdmodel.graphics.shading import PDShading, PDShadingType1


def _function_type2_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    dom = COSArray()
    for v in (0.0, 1.0):
        dom.add(COSFloat(v))
    d.set_item("Domain", dom)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    d.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    d.set_item("C1", c1)
    d.set_int("N", 1)
    return d


def test_shading_type_constant():
    assert PDShadingType1().get_shading_type() == PDShading.SHADING_TYPE1


def test_default_domain_is_unit_square():
    assert PDShadingType1().get_domain().to_float_array() == [0.0, 1.0, 0.0, 1.0]


def test_set_get_function_dispatches_to_subclass():
    s = PDShadingType1()
    s.set_function(_function_type2_dict())
    assert isinstance(s.get_function(), PDFunctionType2)


def test_factory_dispatch_via_pd_shading_create():
    d = COSDictionary()
    d.set_int("ShadingType", 1)
    s = PDShading.create(d)
    assert isinstance(s, PDShadingType1)
