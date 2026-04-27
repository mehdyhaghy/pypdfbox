from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


# ---------- DeviceGray ----------


def test_device_gray_get_initial_color() -> None:
    cs = PDDeviceGray.INSTANCE
    color = cs.get_initial_color()
    assert isinstance(color, PDColor)
    assert color.get_components() == [0.0]
    assert color.get_color_space() is cs


def test_device_gray_get_default_decode() -> None:
    assert PDDeviceGray.INSTANCE.get_default_decode(8) == [0.0, 1.0]


def test_device_gray_get_default_decode_other_bpc() -> None:
    # Default decode does not depend on bpc for DeviceGray.
    assert PDDeviceGray.INSTANCE.get_default_decode(1) == [0.0, 1.0]
    assert PDDeviceGray.INSTANCE.get_default_decode(16) == [0.0, 1.0]


# ---------- DeviceRGB ----------


def test_device_rgb_get_initial_color() -> None:
    cs = PDDeviceRGB.INSTANCE
    color = cs.get_initial_color()
    assert isinstance(color, PDColor)
    assert color.get_components() == [0.0, 0.0, 0.0]
    assert color.get_color_space() is cs


def test_device_rgb_get_default_decode() -> None:
    assert PDDeviceRGB.INSTANCE.get_default_decode(8) == [
        0.0,
        1.0,
        0.0,
        1.0,
        0.0,
        1.0,
    ]


# ---------- DeviceCMYK ----------


def test_device_cmyk_get_initial_color() -> None:
    cs = PDDeviceCMYK.INSTANCE
    color = cs.get_initial_color()
    assert isinstance(color, PDColor)
    assert color.get_components() == [0.0, 0.0, 0.0, 1.0]
    assert color.get_color_space() is cs


def test_device_cmyk_get_default_decode() -> None:
    assert PDDeviceCMYK.INSTANCE.get_default_decode(8) == [0.0, 1.0] * 4


# ---------- base abstract behaviour ----------


def test_base_get_default_decode_raises_not_implemented() -> None:
    # Any subclass that fails to override should hit the base impl, which
    # raises NotImplementedError. Construct a minimal stand-in to exercise
    # PDColorSpace.get_default_decode without touching concrete subclasses.
    class _Stub(PDColorSpace):
        def get_name(self) -> str:
            return "Stub"

        def get_number_of_components(self) -> int:
            return 1

        def get_initial_color(self) -> PDColor:
            return PDColor([0.0], self)

    stub = _Stub()
    with pytest.raises(NotImplementedError):
        stub.get_default_decode(8)
