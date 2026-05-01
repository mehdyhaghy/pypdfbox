from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_stroking_color import (
    SetStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_color_n import (
    SetStrokingColorN,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat, COSName
from pypdfbox.pdmodel.graphics.color import (
    PDColor,
    PDDeviceGray,
    PDDeviceRGB,
    PDPattern,
)


class _GraphicsState:
    def __init__(self, color_space: Any) -> None:
        self.stroking_color = PDColor([0.0], PDDeviceGray.INSTANCE)
        self.stroking_color_space = color_space

    def get_stroking_color(self) -> PDColor:
        return self.stroking_color

    def set_stroking_color(self, color: PDColor) -> None:
        self.stroking_color = color

    def get_stroking_color_space(self) -> Any:
        return self.stroking_color_space


class _Engine(PDFStreamEngine):
    def __init__(self, color_space: Any) -> None:
        super().__init__()
        self.graphics_state = _GraphicsState(color_space)
        self.colors: list[PDColor] = []

    def get_graphics_state(self) -> _GraphicsState:
        return self.graphics_state

    def set_stroking_color(self, color: PDColor) -> None:
        self.colors.append(color)


def test_class_attribute_operator_name() -> None:
    assert SetStrokingColorN.OPERATOR_NAME == "SCN"


def test_get_name_returns_scn_upper() -> None:
    assert SetStrokingColorN().get_name() == "SCN"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetStrokingColorN, OperatorProcessor)


def test_inherits_from_set_stroking_color() -> None:
    """SCN extends SC upstream — preserve that hierarchy in pypdfbox."""
    assert issubclass(SetStrokingColorN, SetStrokingColor)


def test_process_accepts_pure_components() -> None:
    SetStrokingColorN().process(
        Operator.get_operator("SCN"),
        [COSFloat(0.5), COSFloat(0.5), COSFloat(0.5)],
    )


def test_process_accepts_components_followed_by_pattern_name() -> None:
    SetStrokingColorN().process(
        Operator.get_operator("SCN"),
        [
            COSFloat(0.1),
            COSFloat(0.2),
            COSFloat(0.3),
            COSName.get_pdf_name("P1"),
        ],
    )


def test_process_accepts_pattern_name_only() -> None:
    SetStrokingColorN().process(
        Operator.get_operator("SCN"),
        [COSName.get_pdf_name("P0")],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetStrokingColorN().process(Operator.get_operator("SCN"), [])


def test_default_registry_dispatches_scn_upper() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("SCN")
    assert isinstance(handler, SetStrokingColorN)
    registry.process(
        Operator.get_operator("SCN"),
        [COSFloat(0.5), COSName.get_pdf_name("P1")],
    )


def test_process_with_engine_updates_components_in_rgb_space() -> None:
    engine = _Engine(PDDeviceRGB.INSTANCE)
    processor = SetStrokingColorN()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("SCN"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )

    color = engine.graphics_state.stroking_color
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_components() == pytest.approx([0.1, 0.2, 0.3])
    assert engine.colors == [color]


def test_process_with_pattern_color_space_accepts_name_only() -> None:
    """Pattern colour space — SCN bypasses the component-count check."""
    pattern_cs = PDPattern()
    engine = _Engine(pattern_cs)
    processor = SetStrokingColorN()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("SCN"),
        [COSName.get_pdf_name("P0")],
    )

    assert len(engine.colors) == 1
    color = engine.colors[0]
    assert color.get_color_space() is pattern_cs


def test_process_pdfbox_5851_invalid_color_when_pattern_missing() -> None:
    """Non-numeric operand in a non-Pattern colour space should yield an
    invalid PDColor (PDFBOX-5851), not a crash and not a silent skip.

    The invalid sentinel has no components and no colour space; the
    PageDrawer treats this as transparent.
    """
    engine = _Engine(PDDeviceRGB.INSTANCE)
    processor = SetStrokingColorN()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("SCN"),
        [
            COSFloat(0.1),
            COSFloat(0.2),
            COSName.get_pdf_name("P0"),
        ],
    )

    assert len(engine.colors) == 1
    invalid = engine.colors[0]
    assert invalid.get_components() == []
    assert invalid.get_color_space() is None


def test_process_skips_when_too_few_components() -> None:
    engine = _Engine(PDDeviceRGB.INSTANCE)
    processor = SetStrokingColorN()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("SCN"),
        [COSFloat(0.1)],
    )

    assert engine.colors == []
