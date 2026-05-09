from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_color import (
    SetNonStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color_space import (
    SetNonStrokingColorSpace,
)
from pypdfbox.contentstream.operator.color.set_stroking_color import (
    SetStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_color_space import (
    SetStrokingColorSpace,
)
from pypdfbox.cos import COSFloat, COSName
from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceGray, PDDeviceRGB


class _GraphicsStateWithoutSetters:
    def __init__(self) -> None:
        self.non_stroking_color_space = PDDeviceRGB.INSTANCE
        self.stroking_color_space = PDDeviceRGB.INSTANCE
        self.non_stroking_color: PDColor | None = None
        self.stroking_color: PDColor | None = None


class _Resources:
    def __init__(self, color_space: Any | None) -> None:
        self.color_space = color_space

    def get_color_space(self, name: COSName) -> Any | None:
        del name
        return self.color_space


class _Engine(PDFStreamEngine):
    def __init__(self, resources: Any | None = None) -> None:
        super().__init__()
        self.graphics_state = _GraphicsStateWithoutSetters()
        self.resources = resources
        self.non_stroking_colors: list[PDColor] = []
        self.stroking_colors: list[PDColor] = []

    def get_graphics_state(self) -> _GraphicsStateWithoutSetters:
        return self.graphics_state

    def get_resources(self) -> Any | None:
        return self.resources

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.non_stroking_colors.append(color)

    def set_stroking_color(self, color: PDColor) -> None:
        self.stroking_colors.append(color)


def test_non_stroking_color_skips_when_operand_count_too_short() -> None:
    engine = _Engine()
    processor = SetNonStrokingColor()
    engine.add_operator(processor)

    processor.process(Operator.get_operator("sc"), [COSFloat(0.2)])

    assert engine.graphics_state.non_stroking_color is None
    assert engine.non_stroking_colors == []


def test_stroking_color_skips_when_operand_count_too_short() -> None:
    engine = _Engine()
    processor = SetStrokingColor()
    engine.add_operator(processor)

    processor.process(Operator.get_operator("SC"), [COSFloat(0.2)])

    assert engine.graphics_state.stroking_color is None
    assert engine.stroking_colors == []


def test_non_stroking_color_skips_when_any_operand_is_not_number() -> None:
    engine = _Engine()
    processor = SetNonStrokingColor()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("sc"),
        [COSFloat(0.1), COSName.get_pdf_name("Bad"), COSFloat(0.3)],
    )

    assert engine.graphics_state.non_stroking_color is None
    assert engine.non_stroking_colors == []


def test_stroking_color_skips_when_any_operand_is_not_number() -> None:
    engine = _Engine()
    processor = SetStrokingColor()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("SC"),
        [COSFloat(0.1), COSName.get_pdf_name("Bad"), COSFloat(0.3)],
    )

    assert engine.graphics_state.stroking_color is None
    assert engine.stroking_colors == []


def test_non_stroking_color_falls_back_to_graphics_state_attribute() -> None:
    engine = _Engine()
    processor = SetNonStrokingColor()
    engine.add_operator(processor)
    color = PDColor([0.25], PDDeviceGray.INSTANCE)

    processor.set_color(color)

    assert engine.graphics_state.non_stroking_color is color
    assert engine.non_stroking_colors == [color]


def test_stroking_color_falls_back_to_graphics_state_attribute() -> None:
    engine = _Engine()
    processor = SetStrokingColor()
    engine.add_operator(processor)
    color = PDColor([0.25], PDDeviceGray.INSTANCE)

    processor.set_color(color)

    assert engine.graphics_state.stroking_color is color
    assert engine.stroking_colors == [color]


def test_non_stroking_color_space_resolve_without_context_returns_none() -> None:
    processor = SetNonStrokingColorSpace()

    assert (
        processor.resolve_color_space(COSName.get_pdf_name("DeviceRGB"))
        is None
    )


def test_non_stroking_color_space_uses_attribute_fallbacks() -> None:
    engine = _Engine(_Resources(PDDeviceGray.INSTANCE))
    processor = SetNonStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("DeviceGray")],
    )

    color = engine.graphics_state.non_stroking_color
    assert engine.graphics_state.non_stroking_color_space is PDDeviceGray.INSTANCE
    assert color is not None
    assert color.get_color_space() is PDDeviceGray.INSTANCE
    assert engine.non_stroking_colors == [color]


def test_stroking_color_space_uses_attribute_fallbacks() -> None:
    engine = _Engine(_Resources(PDDeviceGray.INSTANCE))
    processor = SetStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("DeviceGray")],
    )

    color = engine.graphics_state.stroking_color
    assert engine.graphics_state.stroking_color_space is PDDeviceGray.INSTANCE
    assert color is not None
    assert color.get_color_space() is PDDeviceGray.INSTANCE
    assert engine.stroking_colors == [color]
