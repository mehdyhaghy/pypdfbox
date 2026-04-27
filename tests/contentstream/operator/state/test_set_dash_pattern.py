from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_dash_pattern import (
    SetDashPattern,
)
from pypdfbox.cos import COSArray, COSFloat, COSInteger


def test_class_advertises_d_operator_name() -> None:
    assert SetDashPattern.OPERATOR_NAME == "d"
    assert SetDashPattern().get_name() == "d"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetDashPattern, OperatorProcessor)


def test_process_with_solid_pattern_does_not_raise() -> None:
    # ``[] 0 d`` — solid line.
    p = SetDashPattern()
    p.process(
        Operator.get_operator("d"), [COSArray(), COSInteger.get(0)]
    )


def test_process_with_dashed_pattern_does_not_raise() -> None:
    # ``[3 2] 0 d`` — 3-on, 2-off pattern.
    p = SetDashPattern()
    array = COSArray()
    array.add(COSFloat(3.0))
    array.add(COSFloat(2.0))
    p.process(
        Operator.get_operator("d"), [array, COSInteger.get(0)]
    )


def test_process_with_zero_operands_does_not_raise() -> None:
    p = SetDashPattern()
    p.process(Operator.get_operator("d"), [])


def test_default_registry_routes_d_to_set_dash_pattern() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("d")
    assert isinstance(handler, SetDashPattern)
    assert handler.get_name() == "d"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(
        Operator.get_operator("d"), [COSArray(), COSInteger.get(0)]
    )
