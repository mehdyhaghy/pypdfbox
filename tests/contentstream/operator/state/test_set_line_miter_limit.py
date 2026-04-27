from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_line_miter_limit import (
    SetLineMiterLimit,
)
from pypdfbox.cos import COSFloat


def test_class_advertises_capital_M_operator_name() -> None:
    assert SetLineMiterLimit.OPERATOR_NAME == "M"
    assert SetLineMiterLimit().get_name() == "M"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetLineMiterLimit, OperatorProcessor)


def test_process_with_one_operand_does_not_raise() -> None:
    p = SetLineMiterLimit()
    p.process(Operator.get_operator("M"), [COSFloat(10.0)])


def test_process_with_zero_operands_does_not_raise() -> None:
    p = SetLineMiterLimit()
    p.process(Operator.get_operator("M"), [])


def test_default_registry_routes_capital_M_to_set_line_miter_limit() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("M")
    assert isinstance(handler, SetLineMiterLimit)
    assert handler.get_name() == "M"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(Operator.get_operator("M"), [COSFloat(4.0)])
