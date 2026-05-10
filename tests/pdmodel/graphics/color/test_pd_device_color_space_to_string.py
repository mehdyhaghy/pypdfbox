"""Hand-written tests for ``PDDeviceColorSpace.to_string``.

Mirrors upstream ``PDDeviceColorSpace.toString()`` (Java lines 29-33):
returns the device color space's PDF name (``DeviceGray`` /
``DeviceRGB`` / ``DeviceCMYK``).
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


def test_to_string_device_gray() -> None:
    cs = PDDeviceGray.INSTANCE
    assert cs.to_string() == cs.get_name()
    assert cs.to_string() == str(cs)


def test_to_string_device_rgb() -> None:
    cs = PDDeviceRGB.INSTANCE
    assert cs.to_string() == cs.get_name()
    assert cs.to_string() == str(cs)


def test_to_string_device_cmyk() -> None:
    cs = PDDeviceCMYK.INSTANCE
    assert cs.to_string() == cs.get_name()
    assert cs.to_string() == str(cs)
