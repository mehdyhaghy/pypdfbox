from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.shading import (
    PDShading,
    PDShadingType6,
    PDShadingType7,
)

PATCH_TYPES = [
    (PDShadingType6, PDShading.SHADING_TYPE6, "Coons"),
    (PDShadingType7, PDShading.SHADING_TYPE7, "tensor-product"),
]


@pytest.mark.parametrize(("cls", "expected_type", "_label"), PATCH_TYPES)
def test_default_constructor_sets_stream_shading_type(cls, expected_type, _label):
    shading = cls()
    backing = shading.get_cos_object()

    assert shading.get_shading_type() == expected_type
    assert isinstance(backing, COSStream)
    assert backing.get_int("ShadingType") == expected_type
    assert isinstance(PDShading.create(backing), cls)


@pytest.mark.parametrize(("cls", "_expected_type", "_label"), PATCH_TYPES)
def test_bits_accessors_write_patch_stream_dictionary(cls, _expected_type, _label):
    shading = cls()

    shading.set_bits_per_coordinate(32)
    shading.set_bits_per_component(16)
    shading.set_bits_per_flag(8)

    backing = shading.get_cos_object()
    assert shading.get_bits_per_coordinate() == 32
    assert shading.get_bits_per_component() == 16
    assert shading.get_bits_per_flag() == 8
    assert backing.get_int("BitsPerCoordinate") == 32
    assert backing.get_int("BitsPerComponent") == 16
    assert backing.get_int("BitsPerFlag") == 8


@pytest.mark.parametrize(("cls", "_expected_type", "_label"), PATCH_TYPES)
def test_decode_arrays_expose_flat_values_and_parameter_pairs(
    cls,
    _expected_type,
    _label,
):
    shading = cls()
    shading.set_decode([0.0, 612.0, 0.0, 792.0, 0.0, 1.0, 0.25, 0.75])

    raw = shading.get_cos_object().get_dictionary_object("Decode")
    assert isinstance(raw, COSArray)
    assert shading.get_decode() == [0.0, 612.0, 0.0, 792.0, 0.0, 1.0, 0.25, 0.75]
    assert shading.get_decode_for_parameter(0) == (0.0, 612.0)
    assert shading.get_decode_for_parameter(1) == (0.0, 792.0)
    assert shading.get_decode_for_parameter(2) == (0.0, 1.0)
    assert shading.get_decode_for_parameter(3) == (0.25, 0.75)
    assert shading.get_decode_for_parameter(4) is None


@pytest.mark.parametrize(("cls", "expected_type", "_label"), PATCH_TYPES)
def test_cos_stream_round_trip_preserves_body_and_metadata(
    cls,
    expected_type,
    _label,
):
    stream = COSStream()
    stream.set_int("ShadingType", expected_type)
    stream.set_data(b"\x00\x01\x02patch-bytes")

    shading = PDShading.create(stream)
    assert isinstance(shading, cls)
    shading.set_bits_per_coordinate(16)
    shading.set_bits_per_component(8)
    shading.set_bits_per_flag(2)
    shading.set_decode([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])

    rewrapped = cls(shading.get_cos_object())
    assert rewrapped.get_cos_object() is stream
    assert stream.to_raw_byte_array() == b"\x00\x01\x02patch-bytes"
    assert rewrapped.get_bits_per_coordinate() == 16
    assert rewrapped.get_bits_per_component() == 8
    assert rewrapped.get_bits_per_flag() == 2
    assert rewrapped.get_decode_for_parameter(2) == (0.0, 1.0)


@pytest.mark.parametrize(("cls", "expected_type", "_label"), PATCH_TYPES)
def test_factory_accepts_plain_dictionary_for_patch_shading(
    cls,
    expected_type,
    _label,
):
    # Upstream PDShading.create constructs PDShadingType4..7 directly from a
    # plain COSDictionary (the mesh constructors take a COSDictionary, not a
    # stream); an earlier stream-required guard here diverged from upstream and
    # was removed in wave 1513 (caught by the ShadingPatternFuzzProbe oracle).
    dictionary = COSDictionary()
    dictionary.set_int("ShadingType", expected_type)
    assert isinstance(PDShading.create(dictionary), cls)

    stream = COSStream()
    stream.set_int("ShadingType", expected_type)
    assert isinstance(PDShading.create(stream), cls)


@pytest.mark.parametrize(("cls", "_expected_type", "_label"), PATCH_TYPES)
def test_malformed_decode_shapes_are_non_throwing(cls, _expected_type, _label):
    shading = cls()
    shading.get_cos_object().set_item("Decode", COSName.get_pdf_name("BadDecode"))

    assert shading.get_decode() is None
    assert shading.get_decode_for_parameter(0) is None

    malformed_pair = COSArray([COSFloat(0.0), COSName.get_pdf_name("NotANumber")])
    shading.get_cos_object().set_item("Decode", malformed_pair)
    assert shading.get_decode_for_parameter(-1) is None
    assert shading.get_decode_for_parameter(0) is None


@pytest.mark.parametrize(("cls", "_expected_type", "label"), PATCH_TYPES)
def test_patch_decode_docstring_states_deferred_geometry_decode(
    cls,
    _expected_type,
    label,
):
    doc = " ".join((cls.__doc__ or "").split())

    assert label in doc
    assert "preserves the encoded patch stream" in doc
    assert "exposes metadata only" in doc
    assert "deferred to rendering" in doc
