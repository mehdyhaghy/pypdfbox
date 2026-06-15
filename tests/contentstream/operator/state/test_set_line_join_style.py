from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_line_join_style import (
    SetLineJoinStyle,
)
from pypdfbox.cos import COSInteger


def test_class_advertises_lowercase_j_operator_name() -> None:
    assert SetLineJoinStyle.OPERATOR_NAME == "j"
    assert SetLineJoinStyle().get_name() == "j"


def test_capital_and_lowercase_handlers_are_distinct() -> None:
    # ``J`` (cap) and ``j`` (join) must NOT collide. Same letter,
    # different graphics-state field per ISO 32000-1 §8.4.3.4.
    from pypdfbox.contentstream.operator.state.set_line_cap_style import (
        SetLineCapStyle,
    )

    assert SetLineCapStyle.OPERATOR_NAME != SetLineJoinStyle.OPERATOR_NAME
    assert SetLineCapStyle is not SetLineJoinStyle


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetLineJoinStyle, OperatorProcessor)


def test_process_with_one_integer_operand_does_not_raise() -> None:
    # Per ISO 32000-1 §8.4.3.4 the operand is one of {0, 1, 2}.
    p = SetLineJoinStyle()
    for join in (0, 1, 2):
        p.process(Operator.get_operator("j"), [COSInteger.get(join)])


def test_process_with_zero_operands_raises_missing_operand() -> None:
    # Matches upstream SetLineJoinStyle: empty operands throw
    # MissingOperandException (oracle-pinned, wave 1534).
    p = SetLineJoinStyle()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("j"), [])


def test_default_registry_routes_lowercase_j_to_set_line_join_style() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("j")
    assert isinstance(handler, SetLineJoinStyle)
    assert handler.get_name() == "j"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(Operator.get_operator("j"), [COSInteger.get(2)])
