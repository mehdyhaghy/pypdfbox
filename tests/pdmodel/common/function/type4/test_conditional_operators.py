"""Tests for the conditional operator class shapes.

Mirrors the OOP layer in
``pypdfbox.pdmodel.common.function.type4.conditional_operators`` (port of
``ConditionalOperators.java``). Behavioural coverage via the parser-driven
dispatcher already exists in ``test_pd_function_type4_opcodes.py``; these
tests pin the *class* contract — execute pops the right number of operands,
runs the matching procedure, and rejects malformed inputs the same way
upstream does.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4.conditional_operators import (
    If,
    IfElse,
)
from pypdfbox.pdmodel.common.function.type4.execution_context import (
    ExecutionContext,
)
from pypdfbox.pdmodel.common.function.type4.instruction_sequence import (
    InstructionSequence,
)
from pypdfbox.pdmodel.common.function.type4.operator import Operator


class _StubOperators:
    """Placeholder operator-set object.

    The conditional operators only invoke ``InstructionSequence.execute`` on
    their procedure operands; the procedures used in these tests are empty
    (or contain only literals), so the operator registry is never consulted.
    """

    def get_operator(self, name: str) -> None:  # pragma: no cover - unused
        return None


def _ctx(*values: object) -> ExecutionContext:
    """Build a context pre-populated with ``values`` on the stack (bottom->top)."""
    ctx = ExecutionContext(_StubOperators())
    ctx.get_stack().extend(values)
    return ctx


def _proc(*literals: object) -> InstructionSequence:
    """Build a literal-only :class:`InstructionSequence` for tests.

    Only int / real / bool literals are added — no operator names — so the
    procedure runs against any registry without needing one configured.
    """
    seq = InstructionSequence()
    for lit in literals:
        if isinstance(lit, bool):
            seq.add_boolean(lit)
        elif isinstance(lit, int):
            seq.add_integer(lit)
        elif isinstance(lit, float):
            seq.add_real(lit)
        else:  # pragma: no cover - test misuse
            raise AssertionError(f"_proc() got unsupported literal {lit!r}")
    return seq


# ---- inheritance shape ---------------------------------------------------


def test_conditional_classes_subclass_operator() -> None:
    for cls in (If, IfElse):
        assert issubclass(cls, Operator)


# ---- If ------------------------------------------------------------------


def test_if_true_runs_procedure() -> None:
    proc = _proc(42)
    ctx = _ctx(True, proc)
    If().execute(ctx)
    assert ctx.get_stack() == [42]


def test_if_false_skips_procedure() -> None:
    proc = _proc(42)
    ctx = _ctx(False, proc)
    If().execute(ctx)
    assert ctx.get_stack() == []


def test_if_consumes_both_operands_when_false() -> None:
    """Even when condition is False, both operands are popped."""
    proc = _proc(99)
    ctx = _ctx("sentinel", False, proc)
    If().execute(ctx)
    assert ctx.get_stack() == ["sentinel"]


def test_if_non_boolean_condition_raises_type_error() -> None:
    proc = _proc()
    ctx = _ctx(1, proc)  # ``1`` is int, not bool — upstream rejects it.
    with pytest.raises(TypeError):
        If().execute(ctx)


def test_if_non_proc_top_raises_type_error() -> None:
    ctx = _ctx(True, 123)
    with pytest.raises(TypeError):
        If().execute(ctx)


# ---- IfElse --------------------------------------------------------------


def test_ifelse_true_runs_proc1() -> None:
    proc1 = _proc(1)
    proc2 = _proc(2)
    ctx = _ctx(True, proc1, proc2)
    IfElse().execute(ctx)
    assert ctx.get_stack() == [1]


def test_ifelse_false_runs_proc2() -> None:
    proc1 = _proc(1)
    proc2 = _proc(2)
    ctx = _ctx(False, proc1, proc2)
    IfElse().execute(ctx)
    assert ctx.get_stack() == [2]


def test_ifelse_consumes_all_three_operands() -> None:
    proc1 = _proc()
    proc2 = _proc()
    ctx = _ctx("sentinel", True, proc1, proc2)
    IfElse().execute(ctx)
    assert ctx.get_stack() == ["sentinel"]


def test_ifelse_non_boolean_condition_raises_type_error() -> None:
    ctx = _ctx(0, _proc(), _proc())
    with pytest.raises(TypeError):
        IfElse().execute(ctx)


def test_ifelse_non_proc_branch_raises_type_error() -> None:
    ctx = _ctx(True, 1, _proc())
    with pytest.raises(TypeError):
        IfElse().execute(ctx)
    ctx = _ctx(True, _proc(), 2)
    with pytest.raises(TypeError):
        IfElse().execute(ctx)
