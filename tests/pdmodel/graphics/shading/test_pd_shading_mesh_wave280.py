from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.shading import (
    PDShading,
    PDShadingType4,
    PDShadingType5,
)

MESH_TYPES = (PDShadingType4, PDShadingType5)


@pytest.mark.parametrize(
    ("cls", "expected_type"),
    [(PDShadingType4, PDShading.SHADING_TYPE4), (PDShadingType5, PDShading.SHADING_TYPE5)],
)
def test_default_mesh_shading_is_typed_stream(cls, expected_type):
    shading = cls()

    assert shading.get_shading_type() == expected_type
    backing = shading.get_cos_object()
    assert isinstance(backing, COSStream)
    assert backing.get_int("ShadingType") == expected_type


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_mesh_bits_accessors_round_trip(cls):
    shading = cls()

    assert shading.get_bits_per_coordinate() == -1
    assert shading.get_bits_per_component() == -1

    shading.set_bits_per_coordinate(16)
    shading.set_bits_per_component(8)

    assert shading.get_bits_per_coordinate() == 16
    assert shading.get_bits_per_component() == 8
    assert shading.get_cos_object().get_int("BitsPerCoordinate") == 16
    assert shading.get_cos_object().get_int("BitsPerComponent") == 8


def test_type4_bits_per_flag_round_trip():
    shading = PDShadingType4()

    assert shading.get_bits_per_flag() == -1

    shading.set_bits_per_flag(2)

    assert shading.get_bits_per_flag() == 2
    assert shading.get_cos_object().get_int("BitsPerFlag") == 2


def test_type5_vertices_per_row_round_trip():
    shading = PDShadingType5()

    assert shading.get_vertices_per_row() == -1

    shading.set_vertices_per_row(4)

    assert shading.get_vertices_per_row() == 4
    assert shading.get_cos_object().get_int("VerticesPerRow") == 4
    assert not hasattr(PDShadingType4(), "get_vertices_per_row")


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_decode_iterable_and_cos_array_shapes(cls):
    shading = cls()
    shading.set_decode([0.0, 72.0, 10.0, 99.0, 0.0, 1.0])

    assert shading.get_decode() == [0.0, 72.0, 10.0, 99.0, 0.0, 1.0]
    assert shading.get_decode_for_parameter(0) == (0.0, 72.0)
    assert shading.get_decode_for_parameter(1) == (10.0, 99.0)
    assert shading.get_decode_for_parameter(2) == (0.0, 1.0)

    raw = COSArray()
    for value in (1.0, 2.0, 3.0, 4.0):
        raw.add(COSFloat(value))

    shading.set_decode(raw)

    assert shading.get_decode() == [1.0, 2.0, 3.0, 4.0]
    assert shading.get_decode_for_parameter(1) == (3.0, 4.0)
    assert shading.get_cos_object().get_dictionary_object("Decode") is raw


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_decode_none_removes_backing_array(cls):
    shading = cls()
    shading.set_decode([0.0, 1.0])

    shading.set_decode(None)

    assert shading.get_decode() is None
    assert shading.get_decode_for_parameter(0) is None
    assert shading.get_cos_object().get_dictionary_object("Decode") is None


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_cos_stream_body_round_trips_through_factory(cls):
    shading = cls()
    stream = shading.get_cos_object()
    assert isinstance(stream, COSStream)
    stream.set_data(b"\x00\x10\x20mesh-bytes")

    recreated = PDShading.create(stream)

    assert isinstance(recreated, cls)
    recreated_stream = recreated.get_cos_object()
    assert isinstance(recreated_stream, COSStream)
    assert recreated_stream.to_byte_array() == b"\x00\x10\x20mesh-bytes"


@pytest.mark.parametrize(
    ("shading_type", "cls"),
    [
        (PDShading.SHADING_TYPE4, PDShadingType4),
        (PDShading.SHADING_TYPE5, PDShadingType5),
    ],
)
def test_factory_accepts_plain_dictionary_for_mesh_types(
    shading_type,
    cls,
):
    # Upstream PDShading.create constructs the mesh PDShadingType4..7 directly
    # from a plain COSDictionary (their constructors take a COSDictionary, not
    # a stream). The earlier stream-required guard diverged from upstream and
    # was removed in wave 1513 (ShadingPatternFuzzProbe oracle).
    plain = COSDictionary()
    plain.set_int("ShadingType", shading_type)

    assert isinstance(PDShading.create(plain), cls)


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_decode_helpers_ignore_malformed_decode_shapes(cls):
    shading = cls()
    shading.get_cos_object().set_item("Decode", COSName.get_pdf_name("Decode"))

    assert shading.get_decode() is None
    assert shading.get_decode_for_parameter(0) is None

    malformed = COSArray()
    malformed.add(COSName.get_pdf_name("NotANumber"))
    malformed.add(COSFloat(1.0))
    shading.get_cos_object().set_item("Decode", malformed)

    assert shading.get_decode() == [0.0, 1.0]
    assert shading.get_decode_for_parameter(0) is None


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_mesh_decode_docstring_describes_stream_decode(cls):
    # Wave 1431: Type 4/5 mesh-stream decoding is implemented (it was a
    # deferred stub before). collect_triangles now decodes the bit-packed
    # mesh into per-vertex points + colours, and the docstring says so.
    doc = cls.__doc__ or ""

    assert "per-vertex points + colours" in doc
    # collect_triangles must be the subclass's own decoder, not the base stub.
    assert "collect_triangles" in cls.__dict__
