"""Hand-written tests for the mesh-shading (Types 4/5/6/7) helper
accessors ``get_decode_for_parameter`` and
``get_number_of_color_components``.

Mirrors upstream ``PDTriangleBasedShadingType.getDecodeForParameter`` and
``getNumberOfColorComponents`` semantics.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.shading import (
    PDShadingType4,
    PDShadingType5,
    PDShadingType6,
    PDShadingType7,
)

MESH_TYPES = [PDShadingType4, PDShadingType5, PDShadingType6, PDShadingType7]


def _function_type2_dict() -> COSDictionary:
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


# ---------- get_decode_for_parameter ----------


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_decode_for_parameter_none_when_decode_absent(cls):
    assert cls().get_decode_for_parameter(0) is None
    assert cls().get_decode_for_parameter(2) is None


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_decode_for_parameter_returns_xy_pairs(cls):
    shading = cls()
    # x: [0, 100], y: [50, 200], r: [0, 1], g: [0, 1], b: [0, 1]
    shading.set_decode([0.0, 100.0, 50.0, 200.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0])

    assert shading.get_decode_for_parameter(0) == (0.0, 100.0)
    assert shading.get_decode_for_parameter(1) == (50.0, 200.0)
    assert shading.get_decode_for_parameter(2) == (0.0, 1.0)
    assert shading.get_decode_for_parameter(3) == (0.0, 1.0)
    assert shading.get_decode_for_parameter(4) == (0.0, 1.0)


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_decode_for_parameter_out_of_range(cls):
    shading = cls()
    # only 2 entries (one pair) — index 0 OK, index 1+ should be None
    shading.set_decode([0.0, 100.0])

    assert shading.get_decode_for_parameter(0) == (0.0, 100.0)
    assert shading.get_decode_for_parameter(1) is None
    assert shading.get_decode_for_parameter(5) is None


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_decode_for_parameter_short_array_returns_none(cls):
    shading = cls()
    # odd-length array — index for last pair is incomplete
    shading.set_decode([0.0, 1.0, 2.0])

    assert shading.get_decode_for_parameter(0) == (0.0, 1.0)
    assert shading.get_decode_for_parameter(1) is None


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_decode_for_parameter_with_integer_entries(cls):
    """Integer entries in /Decode should still convert cleanly to floats."""
    shading = cls()
    arr = COSArray()
    for v in (0, 100, 50, 200):
        arr.add(COSInteger.get(v))
    shading.get_cos_object().set_item("Decode", arr)

    assert shading.get_decode_for_parameter(0) == (0.0, 100.0)
    assert shading.get_decode_for_parameter(1) == (50.0, 200.0)


# ---------- get_number_of_color_components ----------


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_number_of_color_components_minus_one_when_no_function_no_color_space(
    cls,
):
    """No /Function and no /ColorSpace → -1 (mirrors upstream's -1
    sentinel from getInt(... -1) and absent color-space."""
    assert cls().get_number_of_color_components() == -1


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_number_of_color_components_one_when_function_present(cls):
    """/Function present → 1 (function maps a single mesh sample to N
    output components, so the mesh stream encodes only 1 channel)."""
    shading = cls()
    shading.get_cos_object().set_item("Function", _function_type2_dict())

    assert shading.get_number_of_color_components() == 1


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_number_of_color_components_falls_back_to_color_space(cls):
    """No /Function, but /ColorSpace set → use the color-space component count."""
    shading = cls()
    # DeviceRGB always has 3 components.
    shading.set_color_space(PDDeviceRGB.INSTANCE.get_cos_object())

    # raw COSBase isn't a typed PDColorSpace; inject the wrapper directly
    # via the typed helper. Replace get_color_space behavior by assigning
    # to the dict using PDColorSpace name.
    shading.get_cos_object().set_item(
        COSName.get_pdf_name("ColorSpace"),
        PDDeviceRGB.INSTANCE.get_cos_object(),
    )

    # Our get_color_space returns the raw COSBase, so the helper has to
    # walk via PDColorSpace.create. Verify by patching get_color_space to
    # return a typed instance instead.
    shading.get_color_space = lambda: PDDeviceRGB.INSTANCE  # type: ignore[method-assign]

    assert shading.get_number_of_color_components() == 3


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_number_of_color_components_function_takes_priority(cls):
    """When both /Function and /ColorSpace are set, /Function wins (returns 1)."""
    shading = cls()
    shading.get_cos_object().set_item("Function", _function_type2_dict())
    shading.get_color_space = lambda: PDDeviceRGB.INSTANCE  # type: ignore[method-assign]

    assert shading.get_number_of_color_components() == 1


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_number_of_color_components_with_device_n(cls):
    """A 5-component DeviceN color space surfaces the right component count."""
    # Build a DeviceN COS array: [/DeviceN [...names...] alternate tintTransform]
    names = COSArray()
    for n in ("Red", "Green", "Blue", "Spot1", "Spot2"):
        names.add(COSName.get_pdf_name(n))
    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("DeviceN"))
    cs_array.add(names)
    cs_array.add(COSName.get_pdf_name("DeviceRGB"))
    # tint transform — minimal Type 2 function dict
    cs_array.add(_function_type2_dict())

    shading = cls()
    typed = PDDeviceN(cs_array)
    shading.get_color_space = lambda: typed  # type: ignore[method-assign]

    assert shading.get_number_of_color_components() == 5
