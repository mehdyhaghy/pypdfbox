from __future__ import annotations

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_color import (
    SetNonStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color_n import (
    SetNonStrokingColorN,
)
from pypdfbox.contentstream.operator.color.set_stroking_color import (
    SetStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_color_n import (
    SetStrokingColorN,
)
from pypdfbox.contentstream.operator.color.set_stroking_rgb import (
    SetStrokingRGB,
)
from pypdfbox.contentstream.operator.operator_processor import OperatorProcessor
from pypdfbox.cos import COSBase, COSFloat
from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceRGB


class _GraphicsState:
    def __init__(self) -> None:
        self.stroking_color = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
        self.non_stroking_color = PDColor(
            [0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE
        )
        self.stroking_color_space = PDDeviceRGB.INSTANCE
        self.non_stroking_color_space = PDDeviceRGB.INSTANCE

    def get_stroking_color_space(self) -> object:
        return self.stroking_color_space

    def set_stroking_color(self, color: PDColor) -> None:
        self.stroking_color = color

    def get_non_stroking_color_space(self) -> object:
        return self.non_stroking_color_space

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.non_stroking_color = color


class _Engine(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.graphics_state = _GraphicsState()
        self.colors: list[PDColor] = []
        self._color_processing = False

    def get_graphics_state(self) -> _GraphicsState:
        return self.graphics_state

    def set_stroking_color(self, color: PDColor) -> None:
        self.colors.append(color)

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.colors.append(color)

    def is_should_process_color_operators(self) -> bool:
        return self._color_processing


def _rgb_components() -> list[COSBase]:
    return [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)]


@pytest.mark.parametrize(
    ("processor", "operator_name"),
    [
        (SetStrokingRGB(), "RG"),
        (SetStrokingColor(), "SC"),
        (SetNonStrokingColor(), "sc"),
        (SetStrokingColorN(), "SCN"),
        (SetNonStrokingColorN(), "scn"),
    ],
)
def test_wave315_color_setters_skip_when_color_processing_disabled(
    processor: OperatorProcessor, operator_name: str
) -> None:
    engine = _Engine()
    original_stroking = engine.graphics_state.stroking_color
    original_non_stroking = engine.graphics_state.non_stroking_color
    processor.set_context(engine)

    processor.process(Operator.get_operator(operator_name), _rgb_components())

    assert engine.colors == []
    assert engine.graphics_state.stroking_color is original_stroking
    assert engine.graphics_state.non_stroking_color is original_non_stroking
