"""Parity tests for the function-based (Type 1) shading wrapper.

Covers the per-PDF-spec metadata accessors required by PDF 32000-1
§8.7.4.5.2 (Table 79): ``/Domain`` (default ``[0 1 0 1]``), ``/Matrix``
(optional), and ``/Function`` (required, single-function or per-component
array). Round-trips each accessor and verifies the documented defaults
when the entry is absent.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType2,
)
from pypdfbox.pdmodel.graphics.shading import PDShadingType1
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


def test_shading_type_is_one():
    s = PDShadingType1()
    assert s.get_shading_type() == 1
    assert s.get_shading_type() == PDShading.SHADING_TYPE1
    assert s.get_cos_object().get_int("ShadingType") == 1


def test_constructor_with_existing_dictionary_preserves_entries():
    d = COSDictionary()
    d.set_int("ShadingType", 1)
    matrix = COSArray()
    for v in (1.0, 0.0, 0.0, 1.0, 5.0, 7.0):
        matrix.add(COSFloat(v))
    d.set_item("Matrix", matrix)
    s = PDShadingType1(d)
    assert s.get_cos_object() is d
    assert s.get_matrix() is matrix


# ---------- /Domain ----------


def test_domain_none_when_absent():
    # Upstream PDShadingType1.getDomain() delegates to getCOSArray(DOMAIN),
    # which returns null when /Domain is absent — it does NOT materialize the
    # spec default [0 1 0 1] (proven by the wave-1538 oracle).
    s = PDShadingType1()
    assert s.get_domain() is None
    assert s.get_cos_object().get_dictionary_object("Domain") is None


def test_domain_round_trip_from_cos_array():
    s = PDShadingType1()
    arr = COSArray()
    for v in (0.25, 0.75, -1.0, 1.0):
        arr.add(COSFloat(v))
    s.set_domain(arr)
    assert s.get_cos_object().get_dictionary_object("Domain") is arr
    assert s.get_domain().to_float_array() == [0.25, 0.75, -1.0, 1.0]


def test_domain_round_trip_from_iterable():
    s = PDShadingType1()
    s.set_domain([0.0, 0.5, 0.0, 0.5])
    got = s.get_domain()
    assert isinstance(got, COSArray)
    assert got.to_float_array() == [0.0, 0.5, 0.0, 0.5]


def test_domain_set_none_removes_entry():
    s = PDShadingType1()
    s.set_domain([0.0, 1.0, 0.0, 1.0])
    assert s.get_cos_object().get_dictionary_object("Domain") is not None
    s.set_domain(None)
    assert s.get_cos_object().get_dictionary_object("Domain") is None
    # Typed getter returns None when absent (no default materialization),
    # matching upstream getCOSArray(DOMAIN).
    assert s.get_domain() is None


# ---------- /Matrix ----------


def test_matrix_default_when_absent():
    # Spec default is identity but pypdfbox returns None to signal "absent",
    # matching upstream getMatrix() for shading.
    assert PDShadingType1().get_matrix() is None


def test_matrix_round_trip():
    s = PDShadingType1()
    matrix = COSArray()
    for v in (2.0, 0.0, 0.0, 2.0, 10.0, 20.0):
        matrix.add(COSFloat(v))
    s.set_matrix(matrix)
    assert s.get_matrix() is matrix
    assert s.get_matrix().to_float_array() == [2.0, 0.0, 0.0, 2.0, 10.0, 20.0]


def test_matrix_set_none_removes_entry():
    s = PDShadingType1()
    matrix = COSArray()
    for v in (1.0, 0.0, 0.0, 1.0, 0.0, 0.0):
        matrix.add(COSFloat(v))
    s.set_matrix(matrix)
    assert s.get_matrix() is not None
    s.set_matrix(None)
    assert s.get_matrix() is None


# ---------- /Function ----------


def test_function_default_when_absent():
    assert PDShadingType1().get_function() is None
    assert PDShadingType1().get_functions_array() == []


def test_function_returns_pd_function_subclass_when_set():
    s = PDShadingType1()
    raw = _make_function_type2_dict()
    s.set_function(raw)
    got = s.get_function()
    assert isinstance(got, PDFunction)
    assert isinstance(got, PDFunctionType2)
    assert got.get_function_type() == 2
    assert s.get_cos_object().get_dictionary_object("Function") is raw


def test_function_round_trip_from_pd_function():
    s = PDShadingType1()
    func = PDFunctionType2(_make_function_type2_dict())
    s.set_function(func)
    got = s.get_function()
    assert isinstance(got, PDFunctionType2)
    assert (
        s.get_cos_object().get_dictionary_object("Function")
        is func.get_cos_object()
    )


def test_function_set_none_removes_entry():
    s = PDShadingType1()
    s.set_function(_make_function_type2_dict())
    assert s.get_function() is not None
    s.set_function(None)
    assert s.get_function() is None
    assert s.get_cos_object().get_dictionary_object("Function") is None


def test_function_array_round_trip_from_iterable():
    s = PDShadingType1()
    f1 = PDFunctionType2(_make_function_type2_dict())
    f2 = PDFunctionType2(_make_function_type2_dict())
    f3 = PDFunctionType2(_make_function_type2_dict())
    s.set_function([f1, f2, f3])
    raw = s.get_cos_object().get_dictionary_object("Function")
    assert isinstance(raw, COSArray)
    assert raw.size() == 3
    # get_function returns the COSArray as-is for array-form functions.
    assert s.get_function() is raw
    # get_functions_array unpacks each entry into a PDFunction.
    arr = s.get_functions_array()
    assert len(arr) == 3
    assert all(isinstance(f, PDFunctionType2) for f in arr)


def test_function_array_round_trip_from_cos_array():
    s = PDShadingType1()
    arr = COSArray()
    arr.add(_make_function_type2_dict())
    arr.add(_make_function_type2_dict())
    s.set_function(arr)
    assert s.get_cos_object().get_dictionary_object("Function") is arr
    assert s.get_function() is arr
    unwrapped = s.get_functions_array()
    assert len(unwrapped) == 2
    assert all(isinstance(f, PDFunctionType2) for f in unwrapped)


def test_function_single_function_via_get_functions_array():
    s = PDShadingType1()
    raw = _make_function_type2_dict()
    s.set_function(raw)
    arr = s.get_functions_array()
    assert len(arr) == 1
    assert isinstance(arr[0], PDFunctionType2)


def test_function_rejects_unsupported_type():
    s = PDShadingType1()
    with pytest.raises(TypeError):
        s.set_function(42)  # type: ignore[arg-type]


def test_function_iterable_with_invalid_entry_raises():
    s = PDShadingType1()
    with pytest.raises(TypeError):
        s.set_function([_make_function_type2_dict(), 99])  # type: ignore[list-item]
