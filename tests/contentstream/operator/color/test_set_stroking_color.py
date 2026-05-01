from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_stroking_color import (
    SetStrokingColor,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat
from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceGray, PDDeviceRGB


class _GraphicsState:
    def __init__(self) -> None:
        self.stroking_color = PDColor([0.0], PDDeviceGray.INSTANCE)
        self.stroking_color_space = PDDeviceRGB.INSTANCE

    def get_stroking_color(self) -> PDColor:
        return self.stroking_color

    def set_stroking_color(self, color: PDColor) -> None:
        self.stroking_color = color

    def get_stroking_color_space(self) -> Any:
        return self.stroking_color_space


class _Engine(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.graphics_state = _GraphicsState()
        self.colors: list[PDColor] = []

    def get_graphics_state(self) -> _GraphicsState:
        return self.graphics_state

    def set_stroking_color(self, color: PDColor) -> None:
        self.colors.append(color)


def test_class_attribute_operator_name() -> None:
    assert SetStrokingColor.OPERATOR_NAME == "SC"


def test_get_name_returns_sc_upper() -> None:
    assert SetStrokingColor().get_name() == "SC"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetStrokingColor, OperatorProcessor)


def test_process_accepts_one_component_gray_space() -> None:
    SetStrokingColor().process(
        Operator.get_operator("SC"), [COSFloat(0.42)]
    )


def test_process_accepts_three_component_rgb_like() -> None:
    SetStrokingColor().process(
        Operator.get_operator("SC"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )


def test_process_accepts_four_component_cmyk_like() -> None:
    SetStrokingColor().process(
        Operator.get_operator("SC"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0), COSFloat(1.0)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetStrokingColor().process(Operator.get_operator("SC"), [])


def test_default_registry_dispatches_sc_upper() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("SC")
    assert isinstance(handler, SetStrokingColor)
    registry.process(Operator.get_operator("SC"), [COSFloat(0.5)])


def test_get_color_returns_graphics_state_stroking_color() -> None:
    engine = _Engine()
    processor = SetStrokingColor()
    engine.add_operator(processor)

    assert processor.get_color() is engine.graphics_state.stroking_color


def test_set_color_updates_stroking_color_hook_and_graphics_state() -> None:
    engine = _Engine()
    processor = SetStrokingColor()
    engine.add_operator(processor)
    color = PDColor([0.25, 0.5, 0.75], PDDeviceRGB.INSTANCE)

    processor.set_color(color)

    assert engine.colors == [color]
    assert engine.graphics_state.stroking_color is color


def test_get_color_space_returns_graphics_state_stroking_color_space() -> None:
    engine = _Engine()
    processor = SetStrokingColor()
    engine.add_operator(processor)

    assert processor.get_color_space() is PDDeviceRGB.INSTANCE


def test_process_uses_current_stroking_color_space() -> None:
    engine = _Engine()
    processor = SetStrokingColor()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("SC"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )

    color = engine.graphics_state.stroking_color
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_components() == pytest.approx([0.1, 0.2, 0.3])
    assert engine.colors == [color]


def test_public_hooks_without_context_are_no_ops() -> None:
    processor = SetStrokingColor()
    color = PDColor([1.0], PDDeviceGray.INSTANCE)

    assert processor.get_color() is None
    assert processor.get_color_space() is None
    processor.set_color(color)
