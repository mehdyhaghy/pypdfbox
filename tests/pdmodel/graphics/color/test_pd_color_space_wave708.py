from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


class _ZeroComponentSpace(PDColorSpace):
    def get_name(self) -> str:
        return "Empty"

    def get_number_of_components(self) -> int:
        return 0

    def get_initial_color(self) -> PDColor:
        return PDColor([], self)


class _ShortDecodeDeviceRGB(PDColorSpace):
    def get_name(self) -> str:
        return "DeviceRGB"

    def get_number_of_components(self) -> int:
        return 3

    def get_initial_color(self) -> PDColor:
        return PDColor([0.0, 0.0, 0.0], self)

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        return [0.0, 1.0]


def test_create_array_form_device_gray_and_cmyk_singletons() -> None:
    gray = COSArray()
    gray.add(_name("G"))
    cmyk = COSArray()
    cmyk.add(_name("DeviceCMYK"))

    assert PDColorSpace.create(gray) is PDDeviceGray.INSTANCE
    assert PDColorSpace.create(cmyk) is PDDeviceCMYK.INSTANCE


def test_name_property_and_str_delegate_to_get_name() -> None:
    assert PDDeviceRGB.INSTANCE.name == "DeviceRGB"
    assert str(PDDeviceRGB.INSTANCE) == "DeviceRGB"


def test_to_rgb_image_rejects_zero_component_space() -> None:
    with pytest.raises(ValueError, match="Cannot rasterise"):
        _ZeroComponentSpace().to_rgb_image(b"", 1, 1)


def test_to_rgb_image_pads_short_raster_with_zeroes() -> None:
    img = PDDeviceRGB.INSTANCE.to_rgb_image(bytes([255]), 1, 1)

    assert img.mode == "RGB"
    assert img.getpixel((0, 0)) == (255, 0, 0)


def test_to_rgb_image_falls_back_when_decode_array_is_too_short() -> None:
    img = _ShortDecodeDeviceRGB().to_rgb_image(bytes([0, 128, 255]), 1, 1)

    assert img.mode == "RGB"
    assert img.getpixel((0, 0)) == (0, 128, 255)


def test_to_raw_image_uses_native_modes_for_gray_and_cmyk() -> None:
    # PDDeviceGray inherits the base ``to_raw_image`` which returns the
    # raster as a Pillow ``L`` image. PDDeviceCMYK explicitly overrides
    # to return ``None`` — upstream PDDeviceCMYK.java line 148 does the
    # same: "Device CMYK is not specified, as its the colors of whatever
    # device you use. The user should fallback to the RGB image."
    gray = PDDeviceGray.INSTANCE.to_raw_image(bytes([17]), 1, 1)
    cmyk = PDDeviceCMYK.INSTANCE.to_raw_image(bytes([1, 2, 3, 4]), 1, 1)

    assert gray.mode == "L"
    assert gray.getpixel((0, 0)) == 17
    assert cmyk is None


def test_to_raw_image_falls_back_to_rgb_conversion_for_indexed_space() -> None:
    indexed = PDIndexed()
    indexed.set_lookup_data(bytes([255, 0, 0]))
    img = indexed.to_raw_image(bytes([0]), 1, 1)

    assert img.mode == "RGB"
    assert img.getpixel((0, 0)) == (255, 0, 0)


def test_separation_and_device_n_predicates_cover_true_and_false_paths() -> None:
    assert PDDeviceRGB.INSTANCE.is_separation() is False
    assert PDSeparation().is_separation() is True
    assert PDDeviceRGB.INSTANCE.is_device_n() is False
    assert PDDeviceN().is_device_n() is True
