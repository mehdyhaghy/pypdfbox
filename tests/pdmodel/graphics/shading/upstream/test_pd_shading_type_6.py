"""Behavior-parity tests for ``PDShadingType6`` (Coons patch mesh).

Apache PDFBox does not ship a dedicated ``PDShadingType6Test``; these tests
cover the public surface of upstream
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType6.java``
end-to-end. The lite-surface ``to_paint`` / ``generate_patch`` / ``get_bounds``
hooks defer mesh rendering to the rendering cluster — assertions here pin the
documented fallback contracts and the spec-required ``/BitsPerCoordinate``,
``/BitsPerComponent``, ``/BitsPerFlag``, and ``/Decode`` round-trip.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.graphics.shading import PDShadingType6
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading


def _make_function_type2_dict() -> COSDictionary:
    fn = COSDictionary()
    fn.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item("Domain", domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    fn.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    fn.set_item("C1", c1)
    fn.set_int("N", 1)
    return fn


def test_get_shading_type_is_six():
    # Upstream PDShadingType6.getShadingType returns SHADING_TYPE6.
    assert PDShadingType6().get_shading_type() == PDShading.SHADING_TYPE6


def test_default_backing_object_is_a_stream():
    # Upstream Coons mesh streams encode patch data in the body — the
    # default-constructed instance must be backed by a COSStream so the
    # mesh data has a place to live alongside the dictionary entries.
    assert isinstance(PDShadingType6().get_cos_object(), COSStream)


def test_bits_per_coordinate_default_is_unset():
    # Upstream getBitsPerCoordinate returns -1 when the entry is absent
    # (COSDictionary.getInt default).
    assert PDShadingType6().get_bits_per_coordinate() == -1


def test_bits_per_component_default_is_unset():
    assert PDShadingType6().get_bits_per_component() == -1


def test_bits_per_flag_default_is_unset():
    assert PDShadingType6().get_bits_per_flag() == -1


@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16, 24, 32])
def test_bits_per_coordinate_accepts_spec_values(bits):
    # PDF 32000-1 §8.7.4.5.7 Table 88: BitsPerCoordinate ∈ {1, 2, 4, 8, 12, 16, 24, 32}.
    shading = PDShadingType6()
    shading.set_bits_per_coordinate(bits)
    assert shading.get_bits_per_coordinate() == bits
    assert shading.get_cos_object().get_int("BitsPerCoordinate") == bits


@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16])
def test_bits_per_component_accepts_spec_values(bits):
    # PDF 32000-1 §8.7.4.5.7 Table 88: BitsPerComponent ∈ {1, 2, 4, 8, 12, 16}.
    shading = PDShadingType6()
    shading.set_bits_per_component(bits)
    assert shading.get_bits_per_component() == bits


@pytest.mark.parametrize("bits", [2, 4, 8])
def test_bits_per_flag_accepts_spec_values(bits):
    # PDF 32000-1 §8.7.4.5.7 Table 88: BitsPerFlag ∈ {2, 4, 8}.
    shading = PDShadingType6()
    shading.set_bits_per_flag(bits)
    assert shading.get_bits_per_flag() == bits


def test_to_paint_returns_none_lite_surface():
    # Lite-surface stub for upstream PDShadingType6.toPaint.
    shading = PDShadingType6()
    assert shading.to_paint() is None
    assert shading.to_paint(matrix=object()) is None


def test_get_bounds_returns_none_lite_surface():
    # Lite-surface stub for upstream PDShadingType6.getBounds — bounds
    # computation requires walking the encoded patch stream which belongs
    # to the rendering cluster.
    shading = PDShadingType6()
    assert shading.get_bounds() is None
    assert shading.get_bounds(None, None) is None


def test_get_function_returns_none_when_absent():
    assert PDShadingType6().get_function() is None


def test_set_get_function_round_trip():
    shading = PDShadingType6()
    fn_dict = _make_function_type2_dict()
    shading.set_function(fn_dict)
    fn = shading.get_function()
    assert fn is not None
    assert fn.get_function_type() == 2


def test_set_function_with_none_clears_entry():
    shading = PDShadingType6()
    shading.set_function(_make_function_type2_dict())
    shading.set_function(None)
    assert shading.get_function() is None
    assert shading.get_cos_object().get_dictionary_object("Function") is None


def test_set_function_rejects_unsupported_type():
    shading = PDShadingType6()
    with pytest.raises(TypeError):
        shading.set_function(object())


def test_get_decode_returns_none_when_absent():
    assert PDShadingType6().get_decode() is None


def test_set_decode_iterable_round_trip():
    shading = PDShadingType6()
    shading.set_decode([0.0, 100.0, 0.0, 100.0, 0.0, 1.0])
    assert shading.get_decode() == [0.0, 100.0, 0.0, 100.0, 0.0, 1.0]


def test_set_decode_with_cos_array_preserves_instance():
    shading = PDShadingType6()
    arr = COSArray()
    for v in (0.0, 50.0, 0.0, 75.0, 0.0, 1.0):
        arr.add(COSFloat(v))
    shading.set_decode(arr)
    # COSArray identity is preserved (so indirect refs survive).
    assert shading.get_cos_object().get_dictionary_object("Decode") is arr


def test_set_decode_with_none_clears_entry():
    shading = PDShadingType6()
    shading.set_decode([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    shading.set_decode(None)
    assert shading.get_decode() is None


def test_get_decode_for_parameter_returns_xy_then_components():
    shading = PDShadingType6()
    shading.set_decode([0.0, 100.0, 0.0, 200.0, 0.0, 1.0])
    # Index 0: x range, 1: y range, 2: first color component.
    assert shading.get_decode_for_parameter(0) == (0.0, 100.0)
    assert shading.get_decode_for_parameter(1) == (0.0, 200.0)
    assert shading.get_decode_for_parameter(2) == (0.0, 1.0)


def test_get_decode_for_parameter_returns_none_for_missing_index():
    shading = PDShadingType6()
    shading.set_decode([0.0, 1.0, 0.0, 1.0])  # only x + y, no color components
    assert shading.get_decode_for_parameter(2) is None


def test_get_decode_for_parameter_returns_none_for_negative_index():
    shading = PDShadingType6()
    shading.set_decode([0.0, 1.0, 0.0, 1.0])
    assert shading.get_decode_for_parameter(-1) is None


def test_get_number_of_color_components_with_function_returns_one():
    # Upstream: when /Function is present, color count is fixed at 1 from
    # the mesh-stream's perspective (function maps a single sample to N outputs).
    shading = PDShadingType6()
    shading.set_function(_make_function_type2_dict())
    assert shading.get_number_of_color_components() == 1


def test_get_number_of_color_components_without_function_or_cs_is_minus_one():
    # Upstream returns -1 when neither /Function nor a usable color space
    # is available — callers should treat that as "unknown".
    assert PDShadingType6().get_number_of_color_components() == -1


def test_generate_patch_happy_path_returns_descriptor():
    shading = PDShadingType6()
    points = [(float(i), float(i + 1)) for i in range(12)]
    color = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [1.0, 1.0, 0.0],
    ]
    patch = shading.generate_patch(points, color)
    assert patch["kind"] == "coons"
    assert len(patch["points"]) == 12
    assert len(patch["color"]) == 4
    assert patch["points"][0] == (0.0, 1.0)
    assert patch["color"][2] == [0.0, 0.0, 1.0]


def test_generate_patch_rejects_wrong_point_count():
    shading = PDShadingType6()
    points = [(0.0, 0.0)] * 11  # one short of 12 — must reject
    color = [[1.0]] * 4
    with pytest.raises(ValueError, match="12"):
        shading.generate_patch(points, color)


def test_generate_patch_rejects_wrong_color_count():
    shading = PDShadingType6()
    points = [(0.0, 0.0)] * 12
    color = [[1.0]] * 3  # one short of 4 corner colors — must reject
    with pytest.raises(ValueError, match="4"):
        shading.generate_patch(points, color)
