"""Coverage round-out for ``Restore`` (``Q``).

Targets the two missed branches:

* ``context is None`` → silent return (registry-standalone path).
* ``get_graphics_stack_size() <= 1`` → raises
  :class:`EmptyGraphicsStackException` (PDFBOX-161).
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.state.empty_graphics_stack_exception import (  # noqa: E501
    EmptyGraphicsStackException,
)
from pypdfbox.contentstream.operator.state.restore import Restore
from pypdfbox.cos import COSInteger


class _StackEngine(PDFStreamEngine):
    """Engine whose graphics-stack depth and restore call count are
    controllable for testing the branch table on ``Restore``."""

    def __init__(self, depth: int) -> None:
        super().__init__()
        self._depth: int = depth
        self.restore_calls: int = 0

    def get_graphics_stack_size(self) -> int:
        return self._depth

    def restore_graphics_state(self) -> None:
        self.restore_calls += 1
        # Simulate the pop: if we recorded a depth >1 then conceptually
        # one frame leaves the stack.
        if self._depth > 1:
            self._depth -= 1


def test_process_without_context_returns_silently() -> None:
    """No engine bound (registry-standalone): ``Q`` is a quiet no-op
    rather than raising — the empty-stack guard is engine-level."""
    processor = Restore()
    assert processor.get_context() is None
    processor.process(Operator.get_operator("Q"), [])


def test_process_on_single_frame_stack_raises_empty_graphics_stack() -> None:
    """The PDFBOX-161 guard: when the stack only has the root frame,
    ``Q`` raises :class:`EmptyGraphicsStackException`."""
    engine = _StackEngine(depth=1)
    processor = Restore(engine)
    with pytest.raises(EmptyGraphicsStackException) as exc:
        processor.process(Operator.get_operator("Q"), [])
    assert engine.restore_calls == 0
    assert "graphics stack is empty" in str(exc.value)


def test_process_on_zero_depth_stack_raises_empty_graphics_stack() -> None:
    """Defensive: even a zero-depth stack (shouldn't happen in practice
    but handle gracefully) raises the same exception rather than
    silently popping."""
    engine = _StackEngine(depth=0)
    processor = Restore(engine)
    with pytest.raises(EmptyGraphicsStackException):
        processor.process(Operator.get_operator("Q"), [])
    assert engine.restore_calls == 0


def test_process_on_deeper_stack_calls_restore_graphics_state() -> None:
    """When the stack has >1 frame, ``Q`` delegates to
    :meth:`restore_graphics_state` on the engine."""
    engine = _StackEngine(depth=2)
    processor = Restore(engine)
    processor.process(Operator.get_operator("Q"), [])
    assert engine.restore_calls == 1


def test_process_ignores_extra_operands() -> None:
    """``Q`` takes no operands — extras must be tolerated, not raised."""
    engine = _StackEngine(depth=2)
    processor = Restore(engine)
    processor.process(
        Operator.get_operator("Q"), [COSInteger.get(1), COSInteger.get(2)]
    )
    assert engine.restore_calls == 1


def test_get_name_returns_capital_q() -> None:
    """``Q`` is case-sensitive — must not collapse to ``q`` (save)."""
    assert Restore().get_name() == "Q"
    assert Restore.OPERATOR_NAME == "Q"


def test_set_context_late_binding_engages_restore_logic() -> None:
    """An instance constructed standalone can later be bound and then
    enforces the depth check."""
    processor = Restore()
    engine = _StackEngine(depth=1)
    processor.set_context(engine)
    with pytest.raises(EmptyGraphicsStackException):
        processor.process(Operator.get_operator("Q"), [])


def test_empty_graphics_stack_exception_is_oserror_subclass() -> None:
    """Upstream extends ``IOException`` → we extend ``OSError`` per the
    project's test-porting convention."""

    exc: Any = EmptyGraphicsStackException()
    assert isinstance(exc, OSError)
