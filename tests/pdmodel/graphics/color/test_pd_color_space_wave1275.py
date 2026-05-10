"""Wave 1275 parity test for PDColorSpace.create_from_cos_object factory."""

from __future__ import annotations

from pypdfbox.cos import COSName, COSObject
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


def test_create_from_cos_object_unwraps_indirect_device_name() -> None:
    obj = COSObject(7, 0, resolved=COSName.get_pdf_name("DeviceRGB"))
    cs = PDColorSpace.create_from_cos_object(obj)
    assert cs is PDDeviceRGB.INSTANCE


def test_create_from_cos_object_short_form_device_gray() -> None:
    obj = COSObject(9, 0, resolved=COSName.get_pdf_name("G"))
    cs = PDColorSpace.create_from_cos_object(obj)
    assert cs is PDDeviceGray.INSTANCE


def test_create_from_cos_object_alias_matches_private_helper() -> None:
    # The public alias should produce the same result as the existing private
    # helper (both routes converge in the resource-cache short-circuit).
    obj = COSObject(11, 0, resolved=COSName.get_pdf_name("DeviceCMYK"))
    public_result = PDColorSpace.create_from_cos_object(obj)
    private_result = PDColorSpace._create_from_cos_object(obj, None)
    assert public_result is private_result
