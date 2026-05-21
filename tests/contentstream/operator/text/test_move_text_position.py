"""Parity tests for the registry-stub ``MoveTextPosition`` (``Td``).

Targets ``pypdfbox/contentstream/operator/text/move_text_position.py`` —
the lite registry-routing scaffold (engine-coupled positional bookkeeping
ships with the rendering cluster).
"""

from __future__ import annotations

import logging

from pypdfbox.contentstream import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.text.move_text_position import (
    MoveTextPosition,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName


def test_operator_name_constant_is_td() -> None:
    assert MoveTextPosition.OPERATOR_NAME == "Td"


def test_get_name_returns_td() -> None:
    assert MoveTextPosition().get_name() == "Td"


def test_inherits_from_operator_processor() -> None:
    assert issubclass(MoveTextPosition, OperatorProcessor)


def test_process_with_two_numeric_operands_is_silent() -> None:
    """Happy path: ``Td`` ships two numbers — the lite stub logs and
    returns without raising."""
    processor = MoveTextPosition()
    processor.process(
        Operator.get_operator("Td"),
        [COSFloat(10.0), COSFloat(20.0)],
    )


def test_process_with_integer_operands_is_silent() -> None:
    """Integers are valid ``Td`` operands too — no widening required at
    this layer."""
    processor = MoveTextPosition()
    processor.process(
        Operator.get_operator("Td"),
        [COSInteger.get(5), COSInteger.get(-3)],
    )


def test_process_with_zero_operands_does_not_raise() -> None:
    """The lite stub is logging-only; it does not enforce arity. The
    rendering-cluster handler will raise ``MissingOperandException`` once
    real state bookkeeping lands."""
    processor = MoveTextPosition()
    processor.process(Operator.get_operator("Td"), [])


def test_process_with_wrong_typed_operands_does_not_raise() -> None:
    """Lite stub is permissive — wrong-typed operands log + return."""
    processor = MoveTextPosition()
    processor.process(
        Operator.get_operator("Td"),
        [COSName.get_pdf_name("X"), COSName.get_pdf_name("Y")],
    )


def test_process_logs_dispatch_at_debug_level(
    caplog: logging.LogRecord,
) -> None:
    """``_log_invocation`` emits a debug-level record naming the class
    and operator — observable via the standard pytest ``caplog``."""
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    processor = MoveTextPosition()
    processor.process(
        Operator.get_operator("Td"),
        [COSFloat(1.0), COSFloat(2.0)],
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any("MoveTextPosition" in m and "Td" in m for m in messages)


def test_processor_registered_for_td_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("Td")
    assert isinstance(handler, MoveTextPosition)


def test_registry_dispatch_invokes_processor() -> None:
    """The dispatch path looks up + delegates without raising."""
    registry = OperatorRegistry()
    registry.process(
        Operator.get_operator("Td"),
        [COSFloat(1.5), COSFloat(2.5)],
    )


def test_lookup_returns_fresh_instance_per_call() -> None:
    """The registry yields a new processor instance per lookup so
    handler-local state can't leak across dispatches."""
    registry = OperatorRegistry()
    a = registry.lookup("Td")
    b = registry.lookup("Td")
    assert a is not b
    assert isinstance(a, MoveTextPosition)
    assert isinstance(b, MoveTextPosition)


def test_get_context_returns_none_for_standalone_use() -> None:
    """Default construction leaves the engine context unset — the lite
    base returns ``None`` rather than raising."""
    assert MoveTextPosition().get_context() is None
