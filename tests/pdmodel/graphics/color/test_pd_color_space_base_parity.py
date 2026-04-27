from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation


# ---------- get_name ----------


def test_device_rgb_get_name() -> None:
    assert PDDeviceRGB.INSTANCE.get_name() == "DeviceRGB"


def test_device_gray_get_name() -> None:
    assert PDDeviceGray.INSTANCE.get_name() == "DeviceGray"


def test_device_cmyk_get_name() -> None:
    assert PDDeviceCMYK.INSTANCE.get_name() == "DeviceCMYK"


# ---------- is_pattern ----------


def test_device_rgb_is_pattern_false() -> None:
    assert PDDeviceRGB.INSTANCE.is_pattern() is False


def test_pattern_is_pattern_true() -> None:
    assert PDPattern().is_pattern() is True


# ---------- is_indexed ----------


def test_device_rgb_is_indexed_false() -> None:
    assert PDDeviceRGB.INSTANCE.is_indexed() is False


def test_indexed_is_indexed_true() -> None:
    assert PDIndexed().is_indexed() is True


# ---------- is_separation ----------


def test_device_rgb_is_separation_false() -> None:
    assert PDDeviceRGB.INSTANCE.is_separation() is False


def test_separation_is_separation_true() -> None:
    assert PDSeparation().is_separation() is True


# ---------- is_device_n ----------


def test_device_rgb_is_device_n_false() -> None:
    assert PDDeviceRGB.INSTANCE.is_device_n() is False


def test_device_n_is_device_n_true() -> None:
    assert PDDeviceN().is_device_n() is True


# ---------- get_java_color_space ----------


def test_get_java_color_space_returns_none() -> None:
    # Java-AWT-specific upstream API; no Python equivalent.
    assert PDDeviceRGB.INSTANCE.get_java_color_space() is None
    assert PDDeviceGray.INSTANCE.get_java_color_space() is None
    assert PDIndexed().get_java_color_space() is None


# ---------- to_rgb_image / to_raw_image (rendering deferred) ----------


def test_to_rgb_image_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        PDDeviceRGB.INSTANCE.to_rgb_image(b"", 1, 1)


def test_to_raw_image_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        PDDeviceRGB.INSTANCE.to_raw_image(b"", 1, 1)


# ---------- get_array ----------


def test_device_rgb_get_array_is_none() -> None:
    # Name-only device color spaces have no backing array.
    assert PDDeviceRGB.INSTANCE.get_array() is None


def test_indexed_get_array_returns_cos_array() -> None:
    indexed = PDIndexed()
    arr = indexed.get_array()
    assert isinstance(arr, COSArray)
    # Same object as get_cos_object for array-form color spaces.
    assert arr is indexed.get_cos_object()
