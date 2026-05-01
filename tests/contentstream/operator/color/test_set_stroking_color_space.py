from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_stroking_color_space import (
    SetStrokingColorSpace,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSInteger, COSName
from pypdfbox.pdmodel.graphics.color import (
    PDColor,
    PDColorSpace,
    PDDeviceGray,
    PDDeviceRGB,
)


class _FakeResources:
    """Minimal stand-in for :class:`PDResources` that knows enough to
    answer ``get_color_space(name)`` lookups during these unit tests
    without needing a parsed PDF."""

    def __init__(self, table: dict[str, PDColorSpace]) -> None:
        self._table = table

    def get_color_space(
        self, name: COSName, was_default: bool = False
    ) -> PDColorSpace | None:
        del was_default
        return self._table.get(name.get_name())


class _GraphicsState:
    def __init__(self) -> None:
        self.stroking_color_space: PDColorSpace | None = None
        self.stroking_color: PDColor | None = None

    def set_stroking_color_space(self, cs: PDColorSpace) -> None:
        self.stroking_color_space = cs

    def set_stroking_color(self, color: PDColor) -> None:
        self.stroking_color = color


class _Engine(PDFStreamEngine):
    def __init__(self, resources: Any | None) -> None:
        super().__init__()
        self.graphics_state = _GraphicsState()
        self._resources_obj = resources
        self.engine_colors: list[PDColor] = []
        self._color_processing: bool = True

    # PDFStreamEngine surface overrides

    def get_resources(self) -> Any | None:
        return self._resources_obj

    def get_graphics_state(self) -> _GraphicsState:
        return self.graphics_state

    def set_stroking_color(self, color: PDColor) -> None:
        self.engine_colors.append(color)

    def is_should_process_color_operators(self) -> bool:
        return self._color_processing


def test_class_attribute_operator_name() -> None:
    assert SetStrokingColorSpace.OPERATOR_NAME == "CS"


def test_get_name_returns_cs() -> None:
    assert SetStrokingColorSpace().get_name() == "CS"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetStrokingColorSpace, OperatorProcessor)


def test_process_no_raise_with_color_space_name_operand() -> None:
    p = SetStrokingColorSpace()
    p.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("DeviceRGB")],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetStrokingColorSpace().process(Operator.get_operator("CS"), [])


def test_default_registry_dispatches_cs() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("CS")
    assert isinstance(handler, SetStrokingColorSpace)
    registry.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("DeviceGray")],
    )


def test_process_installs_resolved_color_space_on_graphics_state() -> None:
    resources = _FakeResources({"CS1": PDDeviceRGB.INSTANCE})
    engine = _Engine(resources)
    processor = SetStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("CS1")],
    )

    assert engine.graphics_state.stroking_color_space is PDDeviceRGB.INSTANCE


def test_process_resets_stroking_color_to_initial_color() -> None:
    """Upstream sets gs.strokingColor = cs.getInitialColor() right after
    setting the new colour space — verify the same wiring."""
    resources = _FakeResources({"CS1": PDDeviceRGB.INSTANCE})
    engine = _Engine(resources)
    processor = SetStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("CS1")],
    )

    color = engine.graphics_state.stroking_color
    assert color is not None
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    # Engine-side notification mirrors the SC/G/RG/K family.
    assert engine.engine_colors == [color]


def test_process_skips_when_color_processing_disabled() -> None:
    """Mirrors upstream's ``isShouldProcessColorOperators`` early return —
    Type3 charprocs / uncoloured tiling patterns must not mutate state."""
    resources = _FakeResources({"CS1": PDDeviceRGB.INSTANCE})
    engine = _Engine(resources)
    engine._color_processing = False
    processor = SetStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("CS1")],
    )

    assert engine.graphics_state.stroking_color_space is None
    assert engine.engine_colors == []


def test_process_skips_when_operand_is_not_a_name() -> None:
    """Upstream silently returns when the leading operand is not a
    ``COSName`` — never crashes on malformed streams."""
    resources = _FakeResources({"CS1": PDDeviceRGB.INSTANCE})
    engine = _Engine(resources)
    processor = SetStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("CS"),
        [COSInteger.get(1)],
    )

    assert engine.graphics_state.stroking_color_space is None


def test_process_skips_when_resources_missing() -> None:
    engine = _Engine(resources=None)
    processor = SetStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("CS1")],
    )

    assert engine.graphics_state.stroking_color_space is None


def test_process_skips_when_color_space_unresolved() -> None:
    """Resources are present but the named colour space isn't — silent
    no-op (don't poison state with ``None``)."""
    resources = _FakeResources({})
    engine = _Engine(resources)
    processor = SetStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("CS-missing")],
    )

    assert engine.graphics_state.stroking_color_space is None
    assert engine.graphics_state.stroking_color is None


def test_process_supports_devicegray_resolution() -> None:
    resources = _FakeResources(
        {"DeviceGray": PDDeviceGray.INSTANCE}
    )
    engine = _Engine(resources)
    processor = SetStrokingColorSpace()
    engine.add_operator(processor)

    processor.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("DeviceGray")],
    )

    assert engine.graphics_state.stroking_color_space is PDDeviceGray.INSTANCE
