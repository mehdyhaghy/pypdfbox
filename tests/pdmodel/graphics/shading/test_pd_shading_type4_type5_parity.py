from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import PDFunction, PDFunctionType2
from pypdfbox.pdmodel.graphics.shading import PDShadingType4, PDShadingType5


def _make_function_type2_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    domain = COSArray()
    for value in (0.0, 1.0):
        domain.add(COSFloat(value))
    d.set_item("Domain", domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    d.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    d.set_item("C1", c1)
    d.set_int("N", 1)
    return d


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_decode_default_when_absent(cls):
    assert cls().get_decode() is None


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_decode_round_trip_from_iterable(cls):
    shading = cls()
    expected = [0.0, 100.0, 0.0, 100.0, 0.0, 1.0]
    shading.set_decode(expected)

    assert shading.get_decode() == expected
    raw = shading.get_cos_object().get_dictionary_object("Decode")
    assert isinstance(raw, COSArray)
    assert raw.size() == 6


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_decode_round_trip_from_cos_array_preserves_backing_array(cls):
    shading = cls()
    raw = COSArray()
    for value in (0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        raw.add(COSFloat(value))

    shading.set_decode(raw)

    assert shading.get_decode() == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    assert shading.get_cos_object().get_dictionary_object("Decode") is raw


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_decode_set_none_removes_entry(cls):
    shading = cls()
    shading.set_decode([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    assert shading.get_decode() is not None

    shading.set_decode(None)

    assert shading.get_decode() is None
    assert shading.get_cos_object().get_dictionary_object("Decode") is None


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_function_default_when_absent(cls):
    assert cls().get_function() is None


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_function_round_trip_from_pd_function(cls):
    shading = cls()
    function = PDFunctionType2(_make_function_type2_dict())

    shading.set_function(function)

    got = shading.get_function()
    assert isinstance(got, PDFunction)
    assert isinstance(got, PDFunctionType2)
    assert got.get_function_type() == 2
    assert (
        shading.get_cos_object().get_dictionary_object("Function")
        is function.get_cos_object()
    )


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_function_round_trip_from_cos_dictionary(cls):
    shading = cls()
    raw = _make_function_type2_dict()

    shading.set_function(raw)

    assert isinstance(shading.get_function(), PDFunctionType2)
    assert shading.get_cos_object().get_dictionary_object("Function") is raw


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_function_set_none_removes_entry(cls):
    shading = cls()
    shading.set_function(_make_function_type2_dict())
    assert shading.get_function() is not None

    shading.set_function(None)

    assert shading.get_function() is None
    assert shading.get_cos_object().get_dictionary_object("Function") is None


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_function_rejects_unsupported_type(cls):
    with pytest.raises(TypeError):
        cls().set_function(42)  # type: ignore[arg-type]


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_metadata_lives_on_backing_stream(cls):
    shading = cls()
    shading.set_bits_per_coordinate(16)
    shading.set_bits_per_component(8)
    if isinstance(shading, PDShadingType4):
        shading.set_bits_per_flag(2)

    backing = shading.get_cos_object()

    assert isinstance(backing, COSStream)
    assert backing.get_int("BitsPerCoordinate") == 16
    assert backing.get_int("BitsPerComponent") == 8
