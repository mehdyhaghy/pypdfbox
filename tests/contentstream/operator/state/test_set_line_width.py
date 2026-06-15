from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_line_width import SetLineWidth
from pypdfbox.cos import COSFloat


def test_class_advertises_w_operator_name() -> None:
    assert SetLineWidth.OPERATOR_NAME == "w"
    assert SetLineWidth().get_name() == "w"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetLineWidth, OperatorProcessor)


def test_process_with_one_operand_does_not_raise() -> None:
    p = SetLineWidth()
    p.process(Operator.get_operator("w"), [COSFloat(1.5)])


def test_process_with_zero_operands_raises_missing_operand() -> None:
    # Matches upstream SetLineWidth: empty operands throw
    # MissingOperandException (oracle-pinned, wave 1534).
    p = SetLineWidth()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("w"), [])


def test_default_registry_routes_w_to_set_line_width() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("w")
    assert isinstance(handler, SetLineWidth)
    assert handler.get_name() == "w"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    # Should not raise — registry uses lookup + process under the hood.
    registry.process(Operator.get_operator("w"), [COSFloat(2.0)])
