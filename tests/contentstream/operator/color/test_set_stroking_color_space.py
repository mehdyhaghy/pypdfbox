from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_stroking_color_space import (
    SetStrokingColorSpace,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSName


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
