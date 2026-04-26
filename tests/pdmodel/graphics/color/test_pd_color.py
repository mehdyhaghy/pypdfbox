from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern


# ---------- device singletons ----------


def test_device_gray_singleton_metadata() -> None:
    cs = PDDeviceGray.INSTANCE
    assert cs.get_name() == "DeviceGray"
    assert cs.get_number_of_components() == 1
    assert PDDeviceGray.INSTANCE is cs


def test_device_rgb_singleton_metadata() -> None:
    cs = PDDeviceRGB.INSTANCE
    assert cs.get_name() == "DeviceRGB"
    assert cs.get_number_of_components() == 3
    assert PDDeviceRGB.INSTANCE is cs


def test_device_cmyk_singleton_metadata() -> None:
    cs = PDDeviceCMYK.INSTANCE
    assert cs.get_name() == "DeviceCMYK"
    assert cs.get_number_of_components() == 4
    assert PDDeviceCMYK.INSTANCE is cs


def test_device_color_spaces_extend_pd_color_space() -> None:
    assert isinstance(PDDeviceGray.INSTANCE, PDColorSpace)
    assert isinstance(PDDeviceRGB.INSTANCE, PDColorSpace)
    assert isinstance(PDDeviceCMYK.INSTANCE, PDColorSpace)


# ---------- initial colors (black) ----------


def test_device_gray_initial_color_is_black() -> None:
    assert PDDeviceGray.INSTANCE.get_initial_color().get_components() == [0.0]


def test_device_rgb_initial_color_is_black() -> None:
    assert PDDeviceRGB.INSTANCE.get_initial_color().get_components() == [0.0, 0.0, 0.0]


def test_device_cmyk_initial_color_is_black() -> None:
    assert PDDeviceCMYK.INSTANCE.get_initial_color().get_components() == [
        0.0,
        0.0,
        0.0,
        1.0,
    ]


# ---------- device color space CO surface ----------


def test_device_color_space_cos_object_is_name() -> None:
    cos = PDDeviceRGB.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.get_name() == "DeviceRGB"


# ---------- PDColor accessors ----------


def test_pd_color_basic_accessors() -> None:
    color = PDColor([1.0, 0.5, 0.0], PDDeviceRGB.INSTANCE)
    assert color.get_components() == [1.0, 0.5, 0.0]
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_pattern_name() is None
    assert color.is_pattern() is False


def test_pd_color_components_are_defensively_copied() -> None:
    src = [1.0, 0.5, 0.0]
    color = PDColor(src, PDDeviceRGB.INSTANCE)
    src[0] = 99.0
    assert color.get_components() == [1.0, 0.5, 0.0]
    out = color.get_components()
    out[0] = 42.0
    assert color.get_components() == [1.0, 0.5, 0.0]


# ---------- PDColor round-trips ----------


def test_pd_color_to_cos_array_round_trip() -> None:
    original = PDColor([1.0, 0.5, 0.0], PDDeviceRGB.INSTANCE)
    array = original.to_cos_array()
    assert isinstance(array, COSArray)
    assert array.size() == 3
    assert isinstance(array.get(0), COSFloat)
    assert array.to_float_array() == [1.0, 0.5, 0.0]

    restored = PDColor.from_cos_array(array, PDDeviceRGB.INSTANCE)
    assert restored.get_components() == [1.0, 0.5, 0.0]
    assert restored.get_color_space() is PDDeviceRGB.INSTANCE
    assert restored.get_pattern_name() is None


def test_pd_color_with_pattern_name_round_trip() -> None:
    pattern = COSName.get_pdf_name("P1")
    original = PDColor([0.25, 0.75, 0.5], PDDeviceRGB.INSTANCE, pattern)
    assert original.is_pattern() is True

    array = original.to_cos_array()
    assert array.size() == 4
    assert isinstance(array.get(3), COSName)

    restored = PDColor.from_cos_array(array, PDDeviceRGB.INSTANCE)
    assert restored.get_components() == [0.25, 0.75, 0.5]
    assert restored.get_pattern_name() == pattern
    assert restored.is_pattern() is True


def test_pd_color_cmyk_round_trip() -> None:
    # values exact in IEEE-754 float32 to survive COSFloat truncation
    original = PDColor([0.125, 0.25, 0.5, 0.75], PDDeviceCMYK.INSTANCE)
    array = original.to_cos_array()
    restored = PDColor.from_cos_array(array, PDDeviceCMYK.INSTANCE)
    assert restored.get_components() == original.get_components()
    assert restored.get_color_space() is PDDeviceCMYK.INSTANCE


def test_pd_color_gray_round_trip() -> None:
    original = PDColor([0.5], PDDeviceGray.INSTANCE)
    array = original.to_cos_array()
    restored = PDColor.from_cos_array(array, PDDeviceGray.INSTANCE)
    assert restored.get_components() == original.get_components()
    assert restored.get_color_space() is PDDeviceGray.INSTANCE


# ---------- PDColor.to_rgb ----------


def test_to_rgb_device_gray_midtone() -> None:
    rgb = PDColor([0.5], PDDeviceGray.INSTANCE).to_rgb()
    assert rgb == (0.5, 0.5, 0.5)


def test_to_rgb_device_rgb_pure_red() -> None:
    rgb = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE).to_rgb()
    assert rgb == (1.0, 0.0, 0.0)


def test_to_rgb_device_cmyk_pure_red() -> None:
    rgb = PDColor([0.0, 1.0, 1.0, 0.0], PDDeviceCMYK.INSTANCE).to_rgb()
    assert rgb[0] == pytest.approx(1.0, abs=1e-6)
    assert rgb[1] == pytest.approx(0.0, abs=1e-6)
    assert rgb[2] == pytest.approx(0.0, abs=1e-6)


def test_to_rgb_device_cmyk_pure_black_via_k() -> None:
    rgb = PDColor([0.0, 0.0, 0.0, 1.0], PDDeviceCMYK.INSTANCE).to_rgb()
    assert rgb == (0.0, 0.0, 0.0)


def test_to_rgb_lab_white_round_trip() -> None:
    rgb = PDColor([100.0, 0.0, 0.0], PDLab()).to_rgb()
    assert rgb[0] == pytest.approx(1.0, abs=0.05)
    assert rgb[1] == pytest.approx(1.0, abs=0.05)
    assert rgb[2] == pytest.approx(1.0, abs=0.05)


def test_to_rgb_pattern_raises_not_implemented() -> None:
    color = PDColor([], PDPattern(), COSName.get_pdf_name("P1"))
    with pytest.raises(NotImplementedError):
        color.to_rgb()
