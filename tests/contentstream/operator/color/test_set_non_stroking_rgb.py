from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_rgb import (
    SetNonStrokingRGB,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert SetNonStrokingRGB.OPERATOR_NAME == "rg"


def test_get_name_returns_rg_lower() -> None:
    assert SetNonStrokingRGB().get_name() == "rg"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetNonStrokingRGB, OperatorProcessor)


def test_process_no_raise_with_three_components() -> None:
    SetNonStrokingRGB().process(
        Operator.get_operator("rg"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetNonStrokingRGB().process(Operator.get_operator("rg"), [])


def test_default_registry_dispatches_rg_lower() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("rg")
    assert isinstance(handler, SetNonStrokingRGB)
    registry.process(
        Operator.get_operator("rg"),
        [COSFloat(0.9), COSFloat(0.8), COSFloat(0.7)],
    )
