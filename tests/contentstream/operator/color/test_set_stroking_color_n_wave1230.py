from __future__ import annotations

from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from tests.contentstream.operator.color.test_set_stroking_color_n import (
    _GraphicsState,
)


def test_graphics_state_get_stroking_color_returns_current_color() -> None:
    state = _GraphicsState(PDDeviceRGB.INSTANCE)

    assert state.get_stroking_color() is state.stroking_color
