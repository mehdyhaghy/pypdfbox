"""Ported parity tests for the abstract ``PDColorSpace`` base class.

Upstream Apache PDFBox does not ship a dedicated ``PDColorSpaceTest.java``
(coverage of the abstract base lives in subclass tests and integration
tests). The cases here exercise the surface that is genuinely defined on
the base class itself per ``PDColorSpace.java``: ``create`` dispatch,
``createFromCOSObject`` resource-cache plumbing, the abstract ``toRGB``
contract, the protected AWT helpers, and ``getCOSObject``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

# ---------- to_rgb (PDColorSpace.toRGB, line 306) ----------


def test_to_rgb_device_rgb_is_identity() -> None:
    # Upstream PDDeviceRGB.toRGB returns the input unchanged.
    assert PDDeviceRGB.INSTANCE.to_rgb([0.25, 0.5, 0.75]) == [0.25, 0.5, 0.75]


def test_to_rgb_device_gray_replicates_component() -> None:
    assert PDDeviceGray.INSTANCE.to_rgb([0.4]) == [0.4, 0.4, 0.4]


def test_to_rgb_device_cmyk_white() -> None:
    assert PDDeviceCMYK.INSTANCE.to_rgb([0.0, 0.0, 0.0, 0.0]) == [1.0, 1.0, 1.0]


def test_to_rgb_device_cmyk_black_via_k() -> None:
    assert PDDeviceCMYK.INSTANCE.to_rgb([0.0, 0.0, 0.0, 1.0]) == [0.0, 0.0, 0.0]


def test_to_rgb_default_returns_three_floats() -> None:
    # The base-class default delegates to PDColor.to_rgb so even
    # subclasses that don't override (Indexed, Lab, DeviceColorSpace)
    # still answer the contract: 3 floats in [0, 1].
    indexed = PDIndexed()
    rgb = indexed.to_rgb(indexed.get_initial_color().get_components())
    assert len(rgb) == 3
    for channel in rgb:
        assert 0.0 <= channel <= 1.0


# ---------- _create_from_cos_object (PDColorSpace.createFromCOSObject, line 244) ----------


def test_create_from_cos_object_unwraps_referenced_name() -> None:
    # COSObject -> COSName(DeviceRGB) should resolve to the singleton.
    cos_obj = COSObject(1, 0, resolved=COSName.get_pdf_name("DeviceRGB"))
    assert PDColorSpace.create(cos_obj) is PDDeviceRGB.INSTANCE


def test_create_from_cos_object_unwraps_array() -> None:
    # COSObject -> COSArray([/Indexed ...]) -> PDIndexed instance.
    array = COSArray()
    array.add(COSName.get_pdf_name("Indexed"))
    cos_obj = COSObject(2, 0, resolved=array)
    cs = PDColorSpace.create(cos_obj)
    assert isinstance(cs, PDIndexed)


def test_create_from_cos_object_no_resources_returns_none_for_unknown_name() -> None:
    # Without resources, named non-device entries cannot be resolved.
    cos_obj = COSObject(3, 0, resolved=COSName.get_pdf_name("CS0"))
    assert PDColorSpace.create(cos_obj) is None


# ---------- to_rgb_image_awt / to_raw_image_awt stubs ----------


def test_to_rgb_image_awt_delegates_to_to_rgb_image() -> None:
    # The AWT overload has no Python analogue — it ignores the AWT
    # color-space argument and calls through to the regular path.
    from PIL import Image

    raster = bytes([10, 20, 30, 40, 50, 60])  # 2 RGB pixels
    img = PDDeviceRGB.INSTANCE.to_rgb_image_awt(raster, None, 2, 1)
    assert isinstance(img, Image.Image)
    assert img.size == (2, 1)
    assert img.mode == "RGB"


def test_to_raw_image_awt_delegates_to_to_raw_image() -> None:
    from PIL import Image

    raster = bytes([100, 150, 200])
    img = PDDeviceRGB.INSTANCE.to_raw_image_awt(raster, None, 1, 1)
    assert isinstance(img, Image.Image)
    assert img.getpixel((0, 0)) == (100, 150, 200)


# ---------- get_cos_object ----------


def test_get_cos_object_for_array_form_returns_array() -> None:
    indexed = PDIndexed()
    assert indexed.get_cos_object() is indexed.get_array()


def test_get_cos_object_for_device_returns_name() -> None:
    # PDDeviceColorSpace overrides get_cos_object to return the device
    # name (DeviceGray/RGB/CMYK) rather than an array — the COSWriter
    # serialises that name into the resources dictionary.
    obj = PDDeviceGray.INSTANCE.get_cos_object()
    assert obj == COSName.get_pdf_name("DeviceGray")


# ---------- get_default_decode (line 292, default rule) ----------


def test_get_default_decode_repeats_zero_one_per_component() -> None:
    # Default rule from PDColorSpace.getDefaultDecode: [0, 1] per
    # component. PDDeviceRGB has 3 components, so 6 entries.
    assert PDDeviceRGB.INSTANCE.get_default_decode(8) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


# ---------- create dispatch invariants (PDColorSpace.create, line 55) ----------


def test_create_none_returns_none() -> None:
    assert PDColorSpace.create(None) is None


def test_create_unknown_array_head_returns_none() -> None:
    array = COSArray()
    array.add(COSName.get_pdf_name("BogusCS"))
    # Upstream raises IOException; pypdfbox returns None for the
    # structural dispatch and lets callers decide. Documented divergence
    # from upstream — see CHANGES.md.
    assert PDColorSpace.create(array) is None


def test_create_pattern_name_returns_pattern_instance() -> None:
    from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

    cs = PDColorSpace.create(COSName.get_pdf_name("Pattern"))
    assert isinstance(cs, PDPattern)


# ---------- abstract surface guard ----------


def test_pd_color_space_is_abstract() -> None:
    # PDColorSpace cannot be instantiated directly — it inherits from ABC
    # and declares get_name/get_number_of_components/get_initial_color
    # as @abstractmethod.
    with pytest.raises(TypeError):
        PDColorSpace()  # type: ignore[abstract]
