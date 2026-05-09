from __future__ import annotations

from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceRGB
from tests.contentstream.operator.color import test_color_processing_gate_wave315 as gate_mod


def test_wave875_graphics_state_color_accessors_round_trip() -> None:
    state = gate_mod._GraphicsState()  # noqa: SLF001
    stroking = PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE)
    non_stroking = PDColor([0.4, 0.5, 0.6], PDDeviceRGB.INSTANCE)

    assert state.get_stroking_color_space() is PDDeviceRGB.INSTANCE
    assert state.get_non_stroking_color_space() is PDDeviceRGB.INSTANCE

    state.set_stroking_color(stroking)
    state.set_non_stroking_color(non_stroking)

    assert state.stroking_color is stroking
    assert state.non_stroking_color is non_stroking


def test_wave875_engine_helper_methods_record_colors_and_state() -> None:
    engine = gate_mod._Engine()  # noqa: SLF001
    color = PDColor([0.7, 0.8, 0.9], PDDeviceRGB.INSTANCE)

    assert engine.get_graphics_state() is engine.graphics_state
    assert engine.is_should_process_color_operators() is False

    engine.set_stroking_color(color)
    engine.set_non_stroking_color(color)

    assert engine.colors == [color, color]
