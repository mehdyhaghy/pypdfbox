"""Parity tests for the radial-gradient (Type 3) shading wrapper.

Covers the per-PDF-spec metadata accessors required by PDF 32000-1
§8.7.4.5.4 (Table 86): ``/Coords`` (6-element ``[x0 y0 r0 x1 y1 r1]``),
``/Domain`` (default ``[0 1]``), ``/Function`` (required), and ``/Extend``
(default ``[false false]``). Round-trips each accessor and verifies the
documented defaults when the entry is absent.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType2,
)
from pypdfbox.pdmodel.graphics.shading import PDShadingType3
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


def test_shading_type_is_three():
    s = PDShadingType3()
    assert s.get_shading_type() == 3
    assert s.get_shading_type() == PDShading.SHADING_TYPE3
    # Default constructor stamps /ShadingType into the backing dict.
    assert s.get_cos_object().get_int("ShadingType") == 3


# ---------- /Coords ----------


def test_coords_default_when_absent():
    # Per Table 86 /Coords is required; when the dict is fresh the entry is
    # absent, and the typed accessor must return None rather than fabricate
    # a default.
    assert PDShadingType3().get_coords() is None


def test_coords_round_trip():
    s = PDShadingType3()
    coords = COSArray()
    for v in (10.0, 20.0, 5.0, 30.0, 40.0, 15.0):
        coords.add(COSFloat(v))
    s.set_coords(coords)
    got = s.get_coords()
    assert got is coords  # COSArray identity preserved
    assert got.to_float_array() == [10.0, 20.0, 5.0, 30.0, 40.0, 15.0]


def test_coords_set_none_removes_entry():
    s = PDShadingType3()
    coords = COSArray()
    for v in (0.0, 0.0, 0.0, 1.0, 1.0, 1.0):
        coords.add(COSFloat(v))
    s.set_coords(coords)
    assert s.get_coords() is not None
    s.set_coords(None)
    assert s.get_coords() is None
    assert s.get_cos_object().get_dictionary_object("Coords") is None


# ---------- /Domain ----------


def test_domain_none_when_absent():
    # Upstream PDShadingType3.getDomain() (inherited from PDShadingType2)
    # delegates to getCOSArray(DOMAIN), returning null when /Domain is absent —
    # no spec-default [0 1] materialization (proven by the wave-1538 oracle).
    s = PDShadingType3()
    assert s.get_domain() is None
    assert s.get_cos_object().get_dictionary_object("Domain") is None


def test_domain_round_trip_from_cos_array():
    s = PDShadingType3()
    arr = COSArray()
    arr.add(COSFloat(0.25))
    arr.add(COSFloat(0.75))
    s.set_domain(arr)
    assert s.get_cos_object().get_dictionary_object("Domain") is arr
    assert s.get_domain().to_float_array() == [0.25, 0.75]


def test_domain_round_trip_from_iterable():
    s = PDShadingType3()
    s.set_domain([0.25, 0.75])
    got = s.get_domain()
    assert isinstance(got, COSArray)
    assert got.to_float_array() == [0.25, 0.75]


def test_domain_set_none_removes_entry():
    s = PDShadingType3()
    s.set_domain([0.0, 1.0])
    assert s.get_cos_object().get_dictionary_object("Domain") is not None
    s.set_domain(None)
    assert s.get_cos_object().get_dictionary_object("Domain") is None
    # And the typed getter returns None when absent (no default).
    assert s.get_domain() is None


# ---------- /Function ----------


def test_function_default_when_absent():
    assert PDShadingType3().get_function() is None


def test_function_returns_pd_function_subclass_when_set():
    s = PDShadingType3()
    raw = _make_function_type2_dict()
    s.set_function(raw)
    got = s.get_function()
    assert isinstance(got, PDFunction)
    assert isinstance(got, PDFunctionType2)
    assert got.get_function_type() == 2
    assert s.get_cos_object().get_dictionary_object("Function") is raw


def test_function_round_trip_from_pd_function():
    s = PDShadingType3()
    func = PDFunctionType2(_make_function_type2_dict())
    s.set_function(func)
    got = s.get_function()
    assert isinstance(got, PDFunctionType2)
    assert (
        s.get_cos_object().get_dictionary_object("Function")
        is func.get_cos_object()
    )


def test_function_set_none_removes_entry():
    s = PDShadingType3()
    s.set_function(_make_function_type2_dict())
    assert s.get_function() is not None
    s.set_function(None)
    assert s.get_function() is None
    assert s.get_cos_object().get_dictionary_object("Function") is None


def test_function_rejects_unsupported_type():
    s = PDShadingType3()
    with pytest.raises(TypeError):
        s.set_function(42)  # type: ignore[arg-type]


# ---------- /Extend ----------


def _extend_pair(arr):
    return (
        bool(arr.get_object(0).get_value()),
        bool(arr.get_object(1).get_value()),
    )


def test_extend_none_when_absent():
    # Upstream PDShadingType3.getExtend() (inherited from PDShadingType2)
    # delegates to getCOSArray(EXTEND), returning null when /Extend is absent —
    # no spec-default [false false] materialization (wave-1538 oracle).
    assert PDShadingType3().get_extend() is None


@pytest.mark.parametrize(
    "start,end",
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_extend_round_trip(start, end):
    s = PDShadingType3()
    s.set_extend(start, end)
    arr = s.get_extend()
    assert isinstance(arr, COSArray)
    assert arr is s.get_cos_object().get_dictionary_object("Extend")
    assert arr.size() == 2
    assert isinstance(arr.get_object(0), COSBoolean)
    assert isinstance(arr.get_object(1), COSBoolean)
    assert _extend_pair(arr) == (start, end)


def test_extend_truthy_inputs_are_coerced_to_bool():
    # set_extend documents that it coerces via bool(); verify the COS form
    # uses the canonical singletons rather than smuggling raw truthy values
    # into the dictionary.
    s = PDShadingType3()
    s.set_extend(1, 0)  # type: ignore[arg-type]
    arr = s.get_extend()
    assert arr.get_object(0) is COSBoolean.TRUE
    assert arr.get_object(1) is COSBoolean.FALSE


def test_extend_accepts_upstream_cos_array_form():
    s = PDShadingType3()
    arr = COSArray()
    arr.add(COSBoolean.TRUE)
    arr.add(COSBoolean.FALSE)

    s.set_extend(arr)

    assert s.get_cos_object().get_dictionary_object("Extend") is arr
    assert s.get_extend() is arr


def test_extend_single_none_removes_entry():
    s = PDShadingType3()
    s.set_extend(True, True)

    s.set_extend(None)

    assert s.get_cos_object().get_dictionary_object("Extend") is None
    assert s.get_extend() is None
