"""Hand-written tests for :class:`InstructionSequence`."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4 import (
    ExecutionContext,
    InstructionSequence,
    Operators,
)


def test_initial_instructions_empty() -> None:
    seq = InstructionSequence()
    assert seq.get_instructions() == []


def test_add_integer_real_boolean_name_proc() -> None:
    seq = InstructionSequence()
    seq.add_integer(1)
    seq.add_real(2.5)
    seq.add_boolean(True)
    seq.add_name("add")
    child = InstructionSequence()
    seq.add_proc(child)
    assert seq.get_instructions() == [1, 2.5, True, "add", child]


def test_execute_pushes_literals() -> None:
    seq = InstructionSequence()
    seq.add_integer(3)
    seq.add_real(0.5)
    seq.add_boolean(False)
    ctx = ExecutionContext(Operators())
    seq.execute(ctx)
    assert ctx.get_stack() == [3, 0.5, False]


def test_execute_dispatches_operator() -> None:
    seq = InstructionSequence()
    seq.add_integer(2)
    seq.add_integer(3)
    seq.add_name("add")
    ctx = ExecutionContext(Operators())
    seq.execute(ctx)
    # The legacy adapter coerces to float; the result is numeric and
    # equal to 5 either way.
    assert len(ctx.get_stack()) == 1
    assert ctx.get_stack()[0] == 5


def test_unknown_operator_raises() -> None:
    seq = InstructionSequence()
    seq.add_name("bogus_op_xyz")
    ctx = ExecutionContext(Operators())
    with pytest.raises(NotImplementedError):
        seq.execute(ctx)


def test_top_level_proc_is_executed_after_walk() -> None:
    """Mirrors upstream behavior: a procedure left on top of the stack
    after the main walk is executed."""
    seq = InstructionSequence()
    inner = InstructionSequence()
    inner.add_boolean(True)
    seq.add_proc(inner)
    ctx = ExecutionContext(Operators())
    seq.execute(ctx)
    assert ctx.get_stack() == [True]


def test_proc_value_is_pushed_for_if() -> None:
    """A proc that is not on top is left as a value (consumed by an
    ``if`` operator below it)."""
    seq = InstructionSequence()
    seq.add_boolean(True)
    inner = InstructionSequence()
    inner.add_integer(99)
    seq.add_proc(inner)
    seq.add_name("if")
    ctx = ExecutionContext(Operators())
    seq.execute(ctx)
    assert ctx.get_stack() == [99]
