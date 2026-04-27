from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_gray import (
    SetNonStrokingGray,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert SetNonStrokingGray.OPERATOR_NAME == "g"


def test_get_name_returns_g_lower() -> None:
    assert SetNonStrokingGray().get_name() == "g"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetNonStrokingGray, OperatorProcessor)


def test_process_no_raise_with_gray_value() -> None:
    SetNonStrokingGray().process(
        Operator.get_operator("g"),
        [COSFloat(0.75)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetNonStrokingGray().process(Operator.get_operator("g"), [])


def test_default_registry_dispatches_g_lower() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("g")
    assert isinstance(handler, SetNonStrokingGray)
    registry.process(Operator.get_operator("g"), [COSFloat(1.0)])
