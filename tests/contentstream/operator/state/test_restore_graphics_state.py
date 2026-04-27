from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.restore_graphics_state import (
    RestoreGraphicsState,
)


def test_class_advertises_capital_Q_operator_name() -> None:
    assert RestoreGraphicsState.OPERATOR_NAME == "Q"
    assert RestoreGraphicsState().get_name() == "Q"


def test_capital_and_lowercase_handlers_are_distinct() -> None:
    # ``q`` (save) and ``Q`` (restore) must NOT collide. PDF operator
    # names are case-sensitive per ISO 32000-1 §7.8.2.
    from pypdfbox.contentstream.operator.state.save_graphics_state import (
        SaveGraphicsState,
    )

    assert RestoreGraphicsState.OPERATOR_NAME != SaveGraphicsState.OPERATOR_NAME
    assert RestoreGraphicsState is not SaveGraphicsState


def test_is_operator_processor_subclass() -> None:
    assert issubclass(RestoreGraphicsState, OperatorProcessor)


def test_process_with_no_operands_does_not_raise() -> None:
    p = RestoreGraphicsState()
    p.process(Operator.get_operator("Q"), [])


def test_default_registry_routes_capital_Q_to_restore_graphics_state() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("Q")
    assert isinstance(handler, RestoreGraphicsState)
    assert handler.get_name() == "Q"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(Operator.get_operator("Q"), [])
