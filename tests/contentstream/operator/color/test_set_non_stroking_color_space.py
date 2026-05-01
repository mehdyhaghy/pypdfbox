from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_color_space import (
    SetNonStrokingColorSpace,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSInteger, COSName
from pypdfbox.pdmodel.graphics.color import (
    PDColor,
    PDColorSpace,
    PDDeviceCMYK,
    PDDeviceGray,
    PDDeviceRGB,
)


class _FakeResources:
    def __init__(self, table: dict[str, PDColorSpace]) -> None:
        self._table = table

    def get_color_space(
        self, name: COSName, was_default: bool = False
    ) -> PDColorSpace | None:
        del was_default
        return self._table.get(name.get_name())


class _GraphicsState:
    def __init__(self) -> None:
        self.non_stroking_color_space: PDColorSpace | None = None
        self.non_stroking_color: PDColor | None = None

    def set_non_stroking_color_space(self, cs: PDColorSpace) -> None:
        self.non_stroking_color_space = cs

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.non_stroking_color = color


class _Engine(PDFStreamEngine):
    def __init__(self, resources: Any | None) -> None:
        super().__init__()
        self.graphics_state = _GraphicsState()
        self._resources_obj = resources
        self.engine_colors: list[PDColor] = []
        self._color_processing: bool = True

    def get_resources(self) -> Any | None:
        return self._resources_obj

    def get_graphics_state(self) -> _GraphicsState:
        return self.graphics_state

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.engine_colors.append(color)

    def is_should_process_color_operators(self) -> bool:
        return self._color_processing


def test_class_attribute_operator_name() -> None:
    assert SetNonStrokingColorSpace.OPERATOR_NAME == "cs"


def test_get_name_returns_cs_lower() -> None:
    assert SetNonStrokingColorSpace().get_name() == "cs"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetNonStrokingColorSpace, OperatorProcessor)


def test_process_no_raise_with_color_space_name_operand() -> None:
    p = SetNonStrokingColorSpace()
    p.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("DeviceCMYK")],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetNonStrokingColorSpace().process(Operator.get_operator("cs"), [])


def test_default_registry_dispatches_cs_lower() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("cs")
    assert isinstance(handler, SetNonStrokingColorSpace)
    registry.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("DeviceGray")],
    )


def test_process_installs_resolved_color_space_on_graphics_state() -> None:
    resources = _FakeResources({"CS1": PDDeviceCMYK.INSTANCE})
    engine = _Engine(resources)
    processor = SetNonStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("CS1")],
    )

    assert (
        engine.graphics_state.non_stroking_color_space is PDDeviceCMYK.INSTANCE
    )


def test_process_resets_non_stroking_color_to_initial_color() -> None:
    resources = _FakeResources({"CS1": PDDeviceRGB.INSTANCE})
    engine = _Engine(resources)
    processor = SetNonStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("CS1")],
    )

    color = engine.graphics_state.non_stroking_color
    assert color is not None
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert engine.engine_colors == [color]


def test_process_skips_when_color_processing_disabled() -> None:
    resources = _FakeResources({"CS1": PDDeviceRGB.INSTANCE})
    engine = _Engine(resources)
    engine._color_processing = False
    processor = SetNonStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("CS1")],
    )

    assert engine.graphics_state.non_stroking_color_space is None
    assert engine.engine_colors == []


def test_process_skips_when_operand_is_not_a_name() -> None:
    resources = _FakeResources({"CS1": PDDeviceRGB.INSTANCE})
    engine = _Engine(resources)
    processor = SetNonStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("cs"),
        [COSInteger.get(1)],
    )

    assert engine.graphics_state.non_stroking_color_space is None


def test_process_skips_when_resources_missing() -> None:
    engine = _Engine(resources=None)
    processor = SetNonStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("CS1")],
    )

    assert engine.graphics_state.non_stroking_color_space is None


def test_process_skips_when_color_space_unresolved() -> None:
    resources = _FakeResources({})
    engine = _Engine(resources)
    processor = SetNonStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("CS-missing")],
    )

    assert engine.graphics_state.non_stroking_color_space is None
    assert engine.graphics_state.non_stroking_color is None


def test_process_supports_devicegray_resolution() -> None:
    resources = _FakeResources({"DeviceGray": PDDeviceGray.INSTANCE})
    engine = _Engine(resources)
    processor = SetNonStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("DeviceGray")],
    )

    assert (
        engine.graphics_state.non_stroking_color_space is PDDeviceGray.INSTANCE
    )
