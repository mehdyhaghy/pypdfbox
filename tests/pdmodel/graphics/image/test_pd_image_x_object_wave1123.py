from __future__ import annotations

from tests.pdmodel.graphics.image.test_pd_image_x_object_wave426 import (
    _DeviceNColorSpace,
)


def test_wave1123_devicen_fixture_reports_name() -> None:
    assert _DeviceNColorSpace(1).get_name() == "DeviceN"
