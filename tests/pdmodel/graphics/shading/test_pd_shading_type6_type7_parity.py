"""Parity tests for the Coons-patch (Type 6) and tensor-product (Type 7)
patch-mesh shading wrappers.

Covers the per-PDF-spec metadata accessors required by PDF 32000-1
§8.7.4.5.7-8 (Tables 88-89): ``/BitsPerCoordinate``, ``/BitsPerComponent``,
``/BitsPerFlag``, ``/Decode``, and ``/Function``. Round-trips each accessor
and verifies the documented defaults when the entry is absent.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType2,
)
from pypdfbox.pdmodel.graphics.shading import (
    PDShadingType6,
    PDShadingType7,
)


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


# ---------- BitsPerCoordinate ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16, 24, 32])
def test_bits_per_coordinate_round_trip(cls, bits):
    s = cls()
    s.set_bits_per_coordinate(bits)
    assert s.get_bits_per_coordinate() == bits


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_bits_per_coordinate_default_when_absent(cls):
    # COSDictionary.get_int returns -1 when the key is missing; the upstream
    # accessor relies on the same sentinel.
    assert cls().get_bits_per_coordinate() == -1


# ---------- BitsPerComponent ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16])
def test_bits_per_component_round_trip(cls, bits):
    s = cls()
    s.set_bits_per_component(bits)
    assert s.get_bits_per_component() == bits


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_bits_per_component_default_when_absent(cls):
    assert cls().get_bits_per_component() == -1


# ---------- BitsPerFlag ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
@pytest.mark.parametrize("bits", [2, 4, 8])
def test_bits_per_flag_round_trip(cls, bits):
    s = cls()
    s.set_bits_per_flag(bits)
    assert s.get_bits_per_flag() == bits


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_bits_per_flag_default_when_absent(cls):
    assert cls().get_bits_per_flag() == -1


# ---------- Decode ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_decode_default_when_absent(cls):
    assert cls().get_decode() is None


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_decode_round_trip_from_iterable(cls):
    s = cls()
    # 2 * (2 + N) entries: xy pair + 1 color component (N = 1 → 6 floats).
    expected = [0.0, 100.0, 0.0, 100.0, 0.0, 1.0]
    s.set_decode(expected)
    assert s.get_decode() == expected
    # And the underlying COSArray was populated.
    arr = s.get_cos_object().get_dictionary_object("Decode")
    assert isinstance(arr, COSArray)
    assert arr.size() == 6


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_decode_round_trip_from_cos_array(cls):
    s = cls()
    arr = COSArray()
    for v in (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):  # N = 2 → 8 floats
        arr.add(COSFloat(v))
    s.set_decode(arr)
    # COSArray identity preserved (set_item stores it as-is).
    assert s.get_cos_object().get_dictionary_object("Decode") is arr
    # And the typed getter materializes the float view.
    assert s.get_decode() == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_decode_set_none_removes_entry(cls):
    s = cls()
    s.set_decode([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    assert s.get_decode() is not None
    s.set_decode(None)
    assert s.get_decode() is None
    assert s.get_cos_object().get_dictionary_object("Decode") is None


# ---------- Function ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_default_when_absent(cls):
    assert cls().get_function() is None


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_round_trip_from_pd_function(cls):
    s = cls()
    func = PDFunctionType2(_make_function_type2_dict())
    s.set_function(func)
    got = s.get_function()
    assert isinstance(got, PDFunction)
    assert isinstance(got, PDFunctionType2)
    assert got.get_function_type() == 2
    # The COS object stored under /Function is the function's backing dict.
    assert (
        s.get_cos_object().get_dictionary_object("Function")
        is func.get_cos_object()
    )


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_round_trip_from_cos_dictionary(cls):
    s = cls()
    raw = _make_function_type2_dict()
    s.set_function(raw)
    got = s.get_function()
    assert isinstance(got, PDFunctionType2)
    assert s.get_cos_object().get_dictionary_object("Function") is raw


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_set_none_removes_entry(cls):
    s = cls()
    s.set_function(_make_function_type2_dict())
    assert s.get_function() is not None
    s.set_function(None)
    assert s.get_function() is None
    assert s.get_cos_object().get_dictionary_object("Function") is None


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_rejects_unsupported_type(cls):
    s = cls()
    with pytest.raises(TypeError):
        s.set_function(42)  # type: ignore[arg-type]


# ---------- backing-stream sanity ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_metadata_lives_on_backing_stream(cls):
    s = cls()
    s.set_bits_per_coordinate(16)
    s.set_bits_per_component(8)
    s.set_bits_per_flag(4)
    backing = s.get_cos_object()
    # Type 6/7 are stream-based per Tables 88-89.
    assert isinstance(backing, COSStream)
    assert backing.get_int("BitsPerCoordinate") == 16
    assert backing.get_int("BitsPerComponent") == 8
    assert backing.get_int("BitsPerFlag") == 4
