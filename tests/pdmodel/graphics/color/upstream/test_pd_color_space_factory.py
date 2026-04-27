"""Ported parity tests for ``PDColorSpace.create``.

Translated from upstream Apache PDFBox (3.0.x) tests covering the
``PDColorSpace.create(COSBase, PDResources)`` static factory dispatch.

Upstream's own ``PDColorSpaceTest.java`` mostly exercises round-tripping
through full PDF documents (which we can't replicate cheaply at this
layer). The structural dispatch invariants — name/array dispatch,
short-form names from inline images, indirect-object unwrapping, and
named-color-space resolution against ``PDResources/ColorSpace`` — are
ported here as they correspond directly to the Java factory's switch.
"""

from __future__ import annotations

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


# ---------- name-form device color spaces ----------


def test_create_device_gray_name() -> None:
    assert PDColorSpace.create(_name("DeviceGray")) is PDDeviceGray.INSTANCE


def test_create_device_rgb_name() -> None:
    assert PDColorSpace.create(_name("DeviceRGB")) is PDDeviceRGB.INSTANCE


def test_create_device_cmyk_name() -> None:
    assert PDColorSpace.create(_name("DeviceCMYK")) is PDDeviceCMYK.INSTANCE


def test_create_inline_image_short_names() -> None:
    # PDF 32000-1 §8.9.5.1, Table 92 — abbreviated inline-image names.
    assert PDColorSpace.create(_name("G")) is PDDeviceGray.INSTANCE
    assert PDColorSpace.create(_name("RGB")) is PDDeviceRGB.INSTANCE
    assert PDColorSpace.create(_name("CMYK")) is PDDeviceCMYK.INSTANCE


def test_create_pattern_name() -> None:
    cs = PDColorSpace.create(_name("Pattern"))
    assert isinstance(cs, PDPattern)


# ---------- array-form color spaces ----------


def test_create_indexed_array() -> None:
    arr = COSArray()
    arr.add(_name("Indexed"))
    arr.add(_name("DeviceRGB"))
    arr.add(0)
    arr.add(b"")
    assert isinstance(PDColorSpace.create(arr), PDIndexed)


def test_create_separation_array() -> None:
    arr = COSArray()
    arr.add(_name("Separation"))
    arr.add(_name("Spot"))
    arr.add(_name("DeviceGray"))
    assert isinstance(PDColorSpace.create(arr), PDSeparation)


def test_create_device_n_array() -> None:
    arr = COSArray()
    arr.add(_name("DeviceN"))
    names = COSArray()
    names.add(_name("Cyan"))
    arr.add(names)
    arr.add(_name("DeviceCMYK"))
    assert isinstance(PDColorSpace.create(arr), PDDeviceN)


def test_create_icc_based_array() -> None:
    stream = COSStream()
    stream.set_int("N", 3)
    arr = COSArray()
    arr.add(_name("ICCBased"))
    arr.add(stream)
    assert isinstance(PDColorSpace.create(arr), PDICCBased)


def test_create_cal_gray_array() -> None:
    arr = COSArray()
    arr.add(_name("CalGray"))
    arr.add(COSDictionary())
    assert isinstance(PDColorSpace.create(arr), PDCalGray)


def test_create_cal_rgb_array() -> None:
    arr = COSArray()
    arr.add(_name("CalRGB"))
    arr.add(COSDictionary())
    assert isinstance(PDColorSpace.create(arr), PDCalRGB)


def test_create_lab_array() -> None:
    arr = COSArray()
    arr.add(_name("Lab"))
    arr.add(COSDictionary())
    assert isinstance(PDColorSpace.create(arr), PDLab)


def test_create_pattern_array_with_underlying_cs() -> None:
    arr = COSArray()
    arr.add(_name("Pattern"))
    arr.add(_name("DeviceGray"))
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDPattern)
    assert cs.get_underlying_color_space() is PDDeviceGray.INSTANCE


# ---------- COSObject indirection ----------


def test_create_unwraps_cos_object_for_name() -> None:
    indirect = COSObject(1, resolved=_name("DeviceRGB"))
    assert PDColorSpace.create(indirect) is PDDeviceRGB.INSTANCE


def test_create_unwraps_cos_object_for_array() -> None:
    arr = COSArray()
    arr.add(_name("CalRGB"))
    arr.add(COSDictionary())
    indirect = COSObject(2, resolved=arr)
    assert isinstance(PDColorSpace.create(indirect), PDCalRGB)


# ---------- /Resources/ColorSpace lookup ----------


def test_create_named_color_space_resolves_via_resources() -> None:
    resources_dict = COSDictionary()
    cs_dict = COSDictionary()
    cs_dict.set_item(_name("CS0"), _name("DeviceCMYK"))
    resources_dict.set_item(_name("ColorSpace"), cs_dict)
    resources = PDResources(resources_dict)
    assert PDColorSpace.create(_name("CS0"), resources) is PDDeviceCMYK.INSTANCE


def test_create_named_color_space_array_form_via_resources() -> None:
    lab_arr = COSArray()
    lab_arr.add(_name("Lab"))
    lab_arr.add(COSDictionary())
    resources_dict = COSDictionary()
    cs_dict = COSDictionary()
    cs_dict.set_item(_name("CSLab"), lab_arr)
    resources_dict.set_item(_name("ColorSpace"), cs_dict)
    resources = PDResources(resources_dict)
    assert isinstance(PDColorSpace.create(_name("CSLab"), resources), PDLab)


def test_create_unknown_name_without_resources_returns_none() -> None:
    # Upstream Java throws, but for our Python factory we mirror upstream
    # 3.0.x behaviour of returning ``null`` when no resources are
    # available to resolve a non-device name (PDFBox API guards against
    # this at the call site via ``Optional`` checks; we keep ``None``).
    assert PDColorSpace.create(_name("UnknownCS")) is None


def test_create_none_returns_none() -> None:
    # Upstream: PDColorSpace.create((COSBase) null, null) -> throws
    # IOException. The pypdfbox port returns ``None`` so callers can use
    # an Optional-style check (this is one of the documented deviations
    # to keep Python idioms; behaviour for *valid* inputs is unchanged).
    assert PDColorSpace.create(None) is None
