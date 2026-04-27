"""Upstream parity tests for ``PDShadingType3``.

Apache PDFBox 3.0.x has no dedicated ``PDShadingType3Test`` — Type 3
radial-gradient shading is covered upstream through PDF rendering
parity fixtures rather than unit tests on the COS wrapper. The
hand-written tests in
``tests/pdmodel/graphics/shading/test_pd_shading_type3_parity.py``
already cover the COS round-trip surface; the tests below mirror the
structural assertions an upstream-style unit test would perform.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunctionType2
from pypdfbox.pdmodel.graphics.shading import PDShading, PDShadingType3


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
    assert PDShadingType3().get_shading_type() == PDShading.SHADING_TYPE3


def test_default_domain_is_zero_one():
    assert PDShadingType3().get_domain().to_float_array() == [0.0, 1.0]


def test_default_extend_is_false_false():
    assert PDShadingType3().get_extend() == (False, False)


def test_coords_round_trip_radial():
    s = PDShadingType3()
    coords = COSArray()
    for v in (50.0, 50.0, 0.0, 50.0, 50.0, 100.0):
        coords.add(COSFloat(v))
    s.set_coords(coords)
    assert s.get_coords().to_float_array() == [50.0, 50.0, 0.0, 50.0, 50.0, 100.0]


def test_set_get_function_dispatches_to_subclass():
    s = PDShadingType3()
    s.set_function(_function_type2_dict())
    assert isinstance(s.get_function(), PDFunctionType2)


def test_factory_dispatch_via_pd_shading_create():
    d = COSDictionary()
    d.set_int("ShadingType", 3)
    s = PDShading.create(d)
    assert isinstance(s, PDShadingType3)
