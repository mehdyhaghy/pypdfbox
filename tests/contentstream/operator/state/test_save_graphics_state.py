from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.save_graphics_state import (
    SaveGraphicsState,
)


def test_class_advertises_lowercase_q_operator_name() -> None:
    assert SaveGraphicsState.OPERATOR_NAME == "q"
    assert SaveGraphicsState().get_name() == "q"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SaveGraphicsState, OperatorProcessor)


def test_process_with_no_operands_does_not_raise() -> None:
    p = SaveGraphicsState()
    p.process(Operator.get_operator("q"), [])


def test_default_registry_routes_lowercase_q_to_save_graphics_state() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("q")
    assert isinstance(handler, SaveGraphicsState)
    assert handler.get_name() == "q"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(Operator.get_operator("q"), [])
