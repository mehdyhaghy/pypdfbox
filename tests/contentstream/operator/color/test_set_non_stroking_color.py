from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_color import (
    SetNonStrokingColor,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat
from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceGray, PDDeviceRGB


class _GraphicsState:
    def __init__(self) -> None:
        self.non_stroking_color = PDColor([0.0], PDDeviceGray.INSTANCE)
        self.non_stroking_color_space = PDDeviceRGB.INSTANCE

    def get_non_stroking_color(self) -> PDColor:
        return self.non_stroking_color

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.non_stroking_color = color

    def get_non_stroking_color_space(self) -> Any:
        return self.non_stroking_color_space


class _Engine(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.graphics_state = _GraphicsState()
        self.colors: list[PDColor] = []

    def get_graphics_state(self) -> _GraphicsState:
        return self.graphics_state

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.colors.append(color)


def test_class_attribute_operator_name() -> None:
    assert SetNonStrokingColor.OPERATOR_NAME == "sc"


def test_get_name_returns_sc_lower() -> None:
    assert SetNonStrokingColor().get_name() == "sc"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetNonStrokingColor, OperatorProcessor)


def test_process_accepts_one_component_gray_space() -> None:
    SetNonStrokingColor().process(
        Operator.get_operator("sc"), [COSFloat(0.25)]
    )


def test_process_accepts_three_component_rgb_like() -> None:
    SetNonStrokingColor().process(
        Operator.get_operator("sc"),
        [COSFloat(0.4), COSFloat(0.5), COSFloat(0.6)],
    )


def test_process_accepts_four_component_cmyk_like() -> None:
    SetNonStrokingColor().process(
        Operator.get_operator("sc"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3), COSFloat(0.4)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetNonStrokingColor().process(Operator.get_operator("sc"), [])


def test_default_registry_dispatches_sc_lower() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("sc")
    assert isinstance(handler, SetNonStrokingColor)
    registry.process(Operator.get_operator("sc"), [COSFloat(0.5)])


def test_get_color_returns_graphics_state_non_stroking_color() -> None:
    engine = _Engine()
    processor = SetNonStrokingColor()
    engine.add_operator(processor)

    assert processor.get_color() is engine.graphics_state.non_stroking_color


def test_set_color_updates_non_stroking_color_hook_and_graphics_state() -> None:
    engine = _Engine()
    processor = SetNonStrokingColor()
    engine.add_operator(processor)
    color = PDColor([0.25, 0.5, 0.75], PDDeviceRGB.INSTANCE)

    processor.set_color(color)

    assert engine.colors == [color]
    assert engine.graphics_state.non_stroking_color is color


def test_get_color_space_returns_graphics_state_non_stroking_color_space() -> None:
    engine = _Engine()
    processor = SetNonStrokingColor()
    engine.add_operator(processor)

    assert processor.get_color_space() is PDDeviceRGB.INSTANCE


def test_process_uses_current_non_stroking_color_space() -> None:
    engine = _Engine()
    processor = SetNonStrokingColor()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("sc"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )

    color = engine.graphics_state.non_stroking_color
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_components() == pytest.approx([0.1, 0.2, 0.3])
    assert engine.colors == [color]


def test_public_hooks_without_context_are_no_ops() -> None:
    processor = SetNonStrokingColor()
    color = PDColor([1.0], PDDeviceGray.INSTANCE)

    assert processor.get_color() is None
    assert processor.get_color_space() is None
    processor.set_color(color)
