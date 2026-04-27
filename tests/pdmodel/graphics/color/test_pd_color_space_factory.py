from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from pypdfbox.pdmodel.pd_resources import PDResources


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


# ---------- None / unknown ----------


def test_create_none_returns_none() -> None:
    assert PDColorSpace.create(None) is None


def test_create_unknown_name_without_resources_returns_none() -> None:
    assert PDColorSpace.create(_name("CS0")) is None


def test_create_empty_array_returns_none() -> None:
    assert PDColorSpace.create(COSArray()) is None


def test_create_array_without_name_head_returns_none() -> None:
    arr = COSArray()
    arr.add(_name("Indexed"))  # well-formed; control case
    arr2 = COSArray()
    arr2.add(arr)  # head is COSArray, not COSName
    assert PDColorSpace.create(arr2) is None


# ---------- name-form device color spaces ----------


def test_create_device_gray_long_name() -> None:
    assert PDColorSpace.create(_name("DeviceGray")) is PDDeviceGray.INSTANCE


def test_create_device_gray_short_name() -> None:
    # Inline-image short form per PDF 32000-1 §8.9.5.1.
    assert PDColorSpace.create(_name("G")) is PDDeviceGray.INSTANCE


def test_create_device_rgb_long_name() -> None:
    assert PDColorSpace.create(_name("DeviceRGB")) is PDDeviceRGB.INSTANCE


def test_create_device_rgb_short_name() -> None:
    assert PDColorSpace.create(_name("RGB")) is PDDeviceRGB.INSTANCE


def test_create_device_cmyk_long_name() -> None:
    assert PDColorSpace.create(_name("DeviceCMYK")) is PDDeviceCMYK.INSTANCE


def test_create_device_cmyk_short_name() -> None:
    assert PDColorSpace.create(_name("CMYK")) is PDDeviceCMYK.INSTANCE


def test_create_pattern_name_form() -> None:
    cs = PDColorSpace.create(_name("Pattern"))
    assert isinstance(cs, PDPattern)
    # Colored (no underlying CS).
    assert cs.get_underlying_color_space() is None


# ---------- array-form color spaces ----------


def test_create_indexed_long_name() -> None:
    arr = COSArray()
    arr.add(_name("Indexed"))
    arr.add(_name("DeviceRGB"))
    arr.add(0)
    arr.add(b"")
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed)
    assert cs.get_array() is arr


def test_create_indexed_short_name_in_array() -> None:
    arr = COSArray()
    arr.add(_name("I"))
    arr.add(_name("DeviceRGB"))
    arr.add(0)
    arr.add(b"")
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed)


def test_create_separation() -> None:
    arr = COSArray()
    arr.add(_name("Separation"))
    arr.add(_name("MySpot"))
    arr.add(_name("DeviceGray"))
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDSeparation)


def test_create_device_n() -> None:
    arr = COSArray()
    arr.add(_name("DeviceN"))
    names = COSArray()
    names.add(_name("Cyan"))
    names.add(_name("Magenta"))
    arr.add(names)
    arr.add(_name("DeviceCMYK"))
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDDeviceN)


def test_create_icc_based() -> None:
    stream = COSStream()
    stream.set_int("N", 3)
    arr = COSArray()
    arr.add(_name("ICCBased"))
    arr.add(stream)
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDICCBased)


def test_create_cal_gray() -> None:
    arr = COSArray()
    arr.add(_name("CalGray"))
    arr.add(COSDictionary())
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDCalGray)


def test_create_cal_rgb() -> None:
    arr = COSArray()
    arr.add(_name("CalRGB"))
    arr.add(COSDictionary())
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDCalRGB)


def test_create_lab() -> None:
    arr = COSArray()
    arr.add(_name("Lab"))
    arr.add(COSDictionary())
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDLab)


def test_create_pattern_array_form_with_underlying_cs() -> None:
    arr = COSArray()
    arr.add(_name("Pattern"))
    arr.add(_name("DeviceRGB"))
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDPattern)
    assert cs.get_underlying_color_space() is PDDeviceRGB.INSTANCE


def test_create_pattern_array_form_without_underlying_cs() -> None:
    arr = COSArray()
    arr.add(_name("Pattern"))
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDPattern)
    assert cs.get_underlying_color_space() is None


# ---------- array-form fallback to device singletons ----------


def test_create_array_form_device_rgb_falls_back_to_singleton() -> None:
    # Some encoders emit [/DeviceRGB] — dispatch should still pick the
    # singleton.
    arr = COSArray()
    arr.add(_name("DeviceRGB"))
    cs = PDColorSpace.create(arr)
    assert cs is PDDeviceRGB.INSTANCE


# ---------- COSObject indirection ----------


def test_create_unwraps_cos_object_for_name() -> None:
    name = _name("DeviceRGB")
    indirect = COSObject(1, resolved=name)
    assert PDColorSpace.create(indirect) is PDDeviceRGB.INSTANCE


def test_create_unwraps_cos_object_for_array() -> None:
    arr = COSArray()
    arr.add(_name("CalGray"))
    arr.add(COSDictionary())
    indirect = COSObject(2, resolved=arr)
    cs = PDColorSpace.create(indirect)
    assert isinstance(cs, PDCalGray)


def test_create_cos_object_pointing_at_none_returns_none() -> None:
    # Unresolved indirect (no loader, no resolved value) — get_object()
    # returns None, so the factory must short-circuit to None.
    indirect = COSObject(3)
    assert PDColorSpace.create(indirect) is None


# ---------- resources lookup ----------


def test_create_named_color_space_resolves_via_resources() -> None:
    # Page-style /Resources/ColorSpace/CS0 -> /DeviceRGB.
    resources_dict = COSDictionary()
    cs_dict = COSDictionary()
    cs_dict.set_item(_name("CS0"), _name("DeviceRGB"))
    resources_dict.set_item(_name("ColorSpace"), cs_dict)
    resources = PDResources(resources_dict)

    cs = PDColorSpace.create(_name("CS0"), resources)
    assert cs is PDDeviceRGB.INSTANCE


def test_create_named_color_space_array_form_via_resources() -> None:
    # /Resources/ColorSpace/CSLab -> [/Lab <<...>>]
    lab_arr = COSArray()
    lab_arr.add(_name("Lab"))
    lab_arr.add(COSDictionary())
    resources_dict = COSDictionary()
    cs_dict = COSDictionary()
    cs_dict.set_item(_name("CSLab"), lab_arr)
    resources_dict.set_item(_name("ColorSpace"), cs_dict)
    resources = PDResources(resources_dict)

    cs = PDColorSpace.create(_name("CSLab"), resources)
    assert isinstance(cs, PDLab)


def test_create_unknown_name_with_resources_but_missing_entry_returns_none() -> None:
    resources = PDResources()
    assert PDColorSpace.create(_name("Unknown"), resources) is None


def test_create_pattern_name_propagates_resources() -> None:
    resources = PDResources()
    cs = PDColorSpace.create(_name("Pattern"), resources)
    assert isinstance(cs, PDPattern)
    assert cs.get_resources() is resources


# ---------- Pattern array form: nested resolution ----------


def test_create_pattern_array_with_named_underlying_resolves_via_resources() -> None:
    # [/Pattern /CS0]  with /CS0 -> /DeviceCMYK in resources.
    resources_dict = COSDictionary()
    cs_dict = COSDictionary()
    cs_dict.set_item(_name("CS0"), _name("DeviceCMYK"))
    resources_dict.set_item(_name("ColorSpace"), cs_dict)
    resources = PDResources(resources_dict)

    arr = COSArray()
    arr.add(_name("Pattern"))
    arr.add(_name("CS0"))
    cs = PDColorSpace.create(arr, resources)
    assert isinstance(cs, PDPattern)
    assert cs.get_underlying_color_space() is PDDeviceCMYK.INSTANCE


# ---------- defensive ----------


def test_create_unknown_array_head_returns_none() -> None:
    arr = COSArray()
    arr.add(_name("DoesNotExist"))
    arr.add(COSDictionary())
    assert PDColorSpace.create(arr) is None


def test_create_resources_argument_is_optional() -> None:
    # All device dispatch paths must work without ``resources``.
    assert PDColorSpace.create(_name("DeviceGray")) is PDDeviceGray.INSTANCE
    assert PDColorSpace.create(_name("DeviceRGB")) is PDDeviceRGB.INSTANCE
    assert PDColorSpace.create(_name("DeviceCMYK")) is PDDeviceCMYK.INSTANCE


def test_create_returns_distinct_instances_for_array_color_spaces() -> None:
    # Each call yields a fresh wrapper around the supplied COSArray,
    # mirroring upstream's lack of caching at this layer (callers cache
    # via PDResources).
    arr = COSArray()
    arr.add(_name("Lab"))
    arr.add(COSDictionary())
    a = PDColorSpace.create(arr)
    b = PDColorSpace.create(arr)
    assert a is not b
    assert isinstance(a, PDLab)
    assert isinstance(b, PDLab)


def test_create_resources_keyword_position_matches_upstream() -> None:
    # Upstream is positional ``create(COSBase, PDResources)``; our port
    # accepts the same order. Mirror the call shape so accidental reorder
    # in either direction trips the test.
    pytest.importorskip("pypdfbox.pdmodel.pd_resources")
    resources = PDResources()
    assert PDColorSpace.create(_name("DeviceRGB"), resources) is PDDeviceRGB.INSTANCE
