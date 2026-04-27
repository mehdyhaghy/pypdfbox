from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_line_cap_style import (
    SetLineCapStyle,
)
from pypdfbox.cos import COSInteger


def test_class_advertises_capital_J_operator_name() -> None:
    assert SetLineCapStyle.OPERATOR_NAME == "J"
    assert SetLineCapStyle().get_name() == "J"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetLineCapStyle, OperatorProcessor)


def test_process_with_one_integer_operand_does_not_raise() -> None:
    # Per ISO 32000-1 §8.4.3.3 the operand is one of {0, 1, 2}.
    p = SetLineCapStyle()
    for cap in (0, 1, 2):
        p.process(Operator.get_operator("J"), [COSInteger.get(cap)])


def test_process_with_zero_operands_does_not_raise() -> None:
    p = SetLineCapStyle()
    p.process(Operator.get_operator("J"), [])


def test_default_registry_routes_capital_J_to_set_line_cap_style() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("J")
    assert isinstance(handler, SetLineCapStyle)
    assert handler.get_name() == "J"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(Operator.get_operator("J"), [COSInteger.get(1)])
