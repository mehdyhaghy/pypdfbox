"""Parity tests for the axial-gradient (Type 2) shading wrapper.

Covers the per-PDF-spec metadata accessors required by PDF 32000-1
§8.7.4.5.3 (Table 85): ``/Coords`` (4-element ``[x0 y0 x1 y1]``),
``/Domain`` (default ``[0 1]``), ``/Function`` (required), and
``/Extend`` (default ``[false false]``). Round-trips each accessor and
verifies the documented defaults when the entry is absent.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType2,
)
from pypdfbox.pdmodel.graphics.shading import PDShadingType2
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading

# ---------- helpers ----------


def _make_function_type2_dict() -> COSDictionary:
    """Build a minimal Type 2 (exponential-interpolation) function dict."""
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


# ---------- shading-type sanity ----------


def test_shading_type_is_two():
    s = PDShadingType2()
    assert s.get_shading_type() == 2
    assert s.get_shading_type() == PDShading.SHADING_TYPE2
    assert s.get_cos_object().get_int("ShadingType") == 2


# ---------- /Coords ----------


def test_coords_default_when_absent():
    # Per Table 85 /Coords is required; absent => None.
    assert PDShadingType2().get_coords() is None


def test_coords_round_trip():
    s = PDShadingType2()
    coords = COSArray()
    for v in (10.0, 20.0, 30.0, 40.0):
        coords.add(COSFloat(v))
    s.set_coords(coords)
    got = s.get_coords()
    assert got is coords
    assert got.to_float_array() == [10.0, 20.0, 30.0, 40.0]


def test_coords_set_none_removes_entry():
    s = PDShadingType2()
    coords = COSArray()
    for v in (0.0, 0.0, 100.0, 0.0):
        coords.add(COSFloat(v))
    s.set_coords(coords)
    assert s.get_coords() is not None
    s.set_coords(None)
    assert s.get_coords() is None


# ---------- /Domain ----------


def test_domain_none_when_absent():
    # Upstream PDShadingType2.getDomain() delegates to getCOSArray(DOMAIN),
    # returning null when /Domain is absent — no spec-default [0 1]
    # materialization (proven by the wave-1538 oracle).
    s = PDShadingType2()
    assert s.get_domain() is None
    assert s.get_cos_object().get_dictionary_object("Domain") is None


def test_domain_round_trip_from_cos_array():
    s = PDShadingType2()
    arr = COSArray()
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(0.5))
    s.set_domain(arr)
    assert s.get_cos_object().get_dictionary_object("Domain") is arr
    assert s.get_domain().to_float_array() == [0.0, 0.5]


def test_domain_round_trip_from_iterable():
    s = PDShadingType2()
    s.set_domain([0.25, 0.75])
    got = s.get_domain()
    assert isinstance(got, COSArray)
    assert got.to_float_array() == [0.25, 0.75]


def test_domain_set_none_removes_entry():
    s = PDShadingType2()
    s.set_domain([0.0, 1.0])
    assert s.get_cos_object().get_dictionary_object("Domain") is not None
    s.set_domain(None)
    assert s.get_cos_object().get_dictionary_object("Domain") is None
    assert s.get_domain() is None


# ---------- /Function ----------


def test_function_default_when_absent():
    assert PDShadingType2().get_function() is None
    assert PDShadingType2().get_functions_array() == []


def test_function_returns_pd_function_subclass_when_set():
    s = PDShadingType2()
    raw = _make_function_type2_dict()
    s.set_function(raw)
    got = s.get_function()
    assert isinstance(got, PDFunction)
    assert isinstance(got, PDFunctionType2)
    assert got.get_function_type() == 2
    assert s.get_cos_object().get_dictionary_object("Function") is raw


def test_function_round_trip_from_pd_function():
    s = PDShadingType2()
    func = PDFunctionType2(_make_function_type2_dict())
    s.set_function(func)
    got = s.get_function()
    assert isinstance(got, PDFunctionType2)
    assert (
        s.get_cos_object().get_dictionary_object("Function")
        is func.get_cos_object()
    )


def test_function_set_none_removes_entry():
    s = PDShadingType2()
    s.set_function(_make_function_type2_dict())
    assert s.get_function() is not None
    s.set_function(None)
    assert s.get_function() is None
    assert s.get_cos_object().get_dictionary_object("Function") is None


def test_function_array_round_trip():
    s = PDShadingType2()
    f1 = PDFunctionType2(_make_function_type2_dict())
    f2 = PDFunctionType2(_make_function_type2_dict())
    s.set_function([f1, f2])
    raw = s.get_cos_object().get_dictionary_object("Function")
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    assert s.get_function() is raw
    arr = s.get_functions_array()
    assert len(arr) == 2
    assert all(isinstance(f, PDFunctionType2) for f in arr)


def test_function_rejects_unsupported_type():
    s = PDShadingType2()
    with pytest.raises(TypeError):
        s.set_function(42)  # type: ignore[arg-type]


# ---------- /Extend ----------


def _extend_pair(arr):
    # Read a /Extend COSArray as a (start, end) bool pair the way the shading
    # context does (upstream getExtend returns the raw COSArray, not a tuple).
    return (
        bool(arr.get_object(0).get_value()),
        bool(arr.get_object(1).get_value()),
    )


def test_extend_none_when_absent():
    # Upstream PDShadingType2.getExtend() delegates to getCOSArray(EXTEND),
    # returning null when /Extend is absent — no spec-default [false false]
    # materialization, no boolean coercion (proven by the wave-1538 oracle).
    assert PDShadingType2().get_extend() is None


@pytest.mark.parametrize(
    "start,end",
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_extend_round_trip(start, end):
    s = PDShadingType2()
    s.set_extend(start, end)
    arr = s.get_extend()
    assert isinstance(arr, COSArray)
    assert arr is s.get_cos_object().get_dictionary_object("Extend")
    assert arr.size() == 2
    assert isinstance(arr.get_object(0), COSBoolean)
    assert isinstance(arr.get_object(1), COSBoolean)
    assert _extend_pair(arr) == (start, end)


def test_extend_truthy_inputs_are_coerced_to_bool():
    s = PDShadingType2()
    s.set_extend(1, 0)  # type: ignore[arg-type]
    arr = s.get_extend()
    assert arr.get_object(0) is COSBoolean.TRUE
    assert arr.get_object(1) is COSBoolean.FALSE


def test_extend_legacy_cos_array_form_still_accepted():
    # Back-compat: existing callers passing a single COSArray work too.
    s = PDShadingType2()
    legacy = COSArray()
    legacy.add(COSBoolean.TRUE)
    legacy.add(COSBoolean.TRUE)
    s.set_extend(legacy)
    assert s.get_cos_object().get_dictionary_object("Extend") is legacy
    assert s.get_extend() is legacy


def test_extend_single_none_removes_entry():
    s = PDShadingType2()
    s.set_extend(True, True)
    assert s.get_cos_object().get_dictionary_object("Extend") is not None
    s.set_extend(None)
    assert s.get_cos_object().get_dictionary_object("Extend") is None
    assert s.get_extend() is None
