from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_stroking_rgb import (
    SetStrokingRGB,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert SetStrokingRGB.OPERATOR_NAME == "RG"


def test_get_name_returns_rg_upper() -> None:
    assert SetStrokingRGB().get_name() == "RG"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetStrokingRGB, OperatorProcessor)


def test_process_no_raise_with_three_components() -> None:
    SetStrokingRGB().process(
        Operator.get_operator("RG"),
        [COSFloat(1.0), COSFloat(0.5), COSFloat(0.0)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetStrokingRGB().process(Operator.get_operator("RG"), [])


def test_default_registry_dispatches_rg_upper() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("RG")
    assert isinstance(handler, SetStrokingRGB)
    registry.process(
        Operator.get_operator("RG"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )
