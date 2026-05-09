from __future__ import annotations

from tests.pdmodel.graphics.color.test_pd_color_space_wave708 import (
    _ShortDecodeDeviceRGB,
    _ZeroComponentSpace,
)


def test_wave987_zero_component_space_initial_color_uses_empty_components() -> None:
    cs = _ZeroComponentSpace()

    color = cs.get_initial_color()

    assert color.get_components() == []
    assert color.get_color_space() is cs


def test_wave987_short_decode_rgb_initial_color_uses_three_zero_components() -> None:
    cs = _ShortDecodeDeviceRGB()

    color = cs.get_initial_color()

    assert color.get_components() == [0.0, 0.0, 0.0]
    assert color.get_color_space() is cs
