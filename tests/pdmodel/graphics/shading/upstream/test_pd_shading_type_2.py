"""Upstream parity tests for ``PDShadingType2``.

Apache PDFBox 3.0.x has no dedicated ``PDShadingType2Test`` — Type 2
axial-gradient shading is exercised through full-pipeline rendering
parity fixtures rather than unit tests on the COS wrapper. The
hand-written tests in ``tests/pdmodel/graphics/shading/test_pd_shading_type_2.py``
cover the COS round-trip surface that does have direct upstream-API
parity. The tests below mirror the structural assertions an
upstream-style unit test would perform.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import PDFunctionType2
from pypdfbox.pdmodel.graphics.shading import PDShading, PDShadingType2


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
    assert PDShadingType2().get_shading_type() == PDShading.SHADING_TYPE2


def test_domain_none_when_absent():
    # Upstream getDomain() → getCOSArray(DOMAIN) → null when absent; no
    # spec-default [0 1] materialization (wave-1538 oracle).
    assert PDShadingType2().get_domain() is None


def test_extend_none_when_absent():
    # Upstream getExtend() → getCOSArray(EXTEND) → null when absent; no
    # spec-default [false false] materialization (wave-1538 oracle).
    assert PDShadingType2().get_extend() is None


def test_coords_round_trip_axial():
    s = PDShadingType2()
    coords = COSArray()
    for v in (0.0, 0.0, 100.0, 0.0):
        coords.add(COSFloat(v))
    s.set_coords(coords)
    assert s.get_coords().to_float_array() == [0.0, 0.0, 100.0, 0.0]


def test_set_get_function_dispatches_to_subclass():
    s = PDShadingType2()
    s.set_function(_function_type2_dict())
    assert isinstance(s.get_function(), PDFunctionType2)


def test_extend_round_trip_two_arg_form():
    s = PDShadingType2()
    s.set_extend(True, False)
    arr = s.get_cos_object().get_dictionary_object("Extend")
    assert isinstance(arr, COSArray)
    assert arr.get_object(0) is COSBoolean.TRUE
    assert arr.get_object(1) is COSBoolean.FALSE


def test_factory_dispatch_via_pd_shading_create():
    d = COSDictionary()
    d.set_int("ShadingType", 2)
    s = PDShading.create(d)
    assert isinstance(s, PDShadingType2)
