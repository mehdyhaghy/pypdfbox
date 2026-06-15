from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_flatness import SetFlatness
from pypdfbox.cos import COSFloat


def test_class_advertises_lowercase_i_operator_name() -> None:
    assert SetFlatness.OPERATOR_NAME == "i"
    assert SetFlatness().get_name() == "i"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetFlatness, OperatorProcessor)


def test_process_with_one_operand_does_not_raise() -> None:
    # ISO 32000-1 §10.6.2: flatness in the range 0..100.
    p = SetFlatness()
    for f in (0.0, 1.0, 100.0):
        p.process(Operator.get_operator("i"), [COSFloat(f)])


def test_process_with_zero_operands_raises_missing_operand() -> None:
    # Matches upstream SetFlatness: an empty operand list throws
    # MissingOperandException (oracle-pinned, wave 1534).
    p = SetFlatness()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("i"), [])


def test_default_registry_routes_lowercase_i_to_set_flatness() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("i")
    assert isinstance(handler, SetFlatness)
    assert handler.get_name() == "i"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(Operator.get_operator("i"), [COSFloat(1.0)])
