from __future__ import annotations

from tests.pdmodel.graphics.image.test_image_color_tail_wave794 import (
    _ArraylessDeviceColor,
)


def test_wave985_arrayless_device_color_helper_methods_are_exercised() -> None:
    color_space = _ArraylessDeviceColor()

    assert color_space.get_number_of_components() == 1
    assert color_space.get_initial_color() is not color_space.get_initial_color()
