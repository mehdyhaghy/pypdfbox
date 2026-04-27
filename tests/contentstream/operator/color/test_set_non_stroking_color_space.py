from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_color_space import (
    SetNonStrokingColorSpace,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSName


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
