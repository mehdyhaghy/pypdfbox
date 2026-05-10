"""Upstream-shaped tests ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestOperators.java``
(``testIf`` line 454, ``testIfElse`` line 471).

Upstream uses ``InstructionSequenceBuilder.parse("...")`` to build the
procedure operand. We construct the equivalent ``InstructionSequence``
directly so these tests stay decoupled from the parser; the *operator*
behaviour under test is identical.

Procedures with arithmetic operators (e.g. ``{ 2 1 add }``) need an
:class:`Operators` registry on the :class:`ExecutionContext`. We use the real
registry from :mod:`pypdfbox.pdmodel.common.function.type4.operators` so the
nested execution exercises the same dispatch path upstream uses.
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
from pypdfbox.pdmodel.common.function.type4.operators import Operators


def _ctx() -> ExecutionContext:
    return ExecutionContext(Operators())


def _proc_2_1_add() -> InstructionSequence:
    """Build the procedure ``{ 2 1 add }`` from upstream's testIf."""
    seq = InstructionSequence()
    seq.add_integer(2)
    seq.add_integer(1)
    seq.add_name("add")
    return seq


def _proc_2_1_sub() -> InstructionSequence:
    """Build the procedure ``{ 2 1 sub }`` from upstream's testIfElse."""
    seq = InstructionSequence()
    seq.add_integer(2)
    seq.add_integer(1)
    seq.add_name("sub")
    return seq


def test_if() -> None:
    """Ported from ``TestOperators.testIf`` (line 454).

    Java cases:
      * ``"true { 2 1 add } if"`` → pops 3, then empty.
      * ``"false { 2 1 add } if"`` → empty.
      * ``"0 { 2 1 add } if"`` → ClassCastException (TypeError here).
    """
    # true branch runs the procedure
    ctx = _ctx()
    ctx.get_stack().extend([True, _proc_2_1_add()])
    If().execute(ctx)
    assert ctx.get_stack() == [3]

    # false branch leaves the stack empty
    ctx = _ctx()
    ctx.get_stack().extend([False, _proc_2_1_add()])
    If().execute(ctx)
    assert ctx.get_stack() == []

    # non-boolean condition raises (Java throws ClassCastException)
    ctx = _ctx()
    ctx.get_stack().extend([0, _proc_2_1_add()])
    with pytest.raises(TypeError):
        If().execute(ctx)


def test_if_else() -> None:
    """Ported from ``TestOperators.testIfElse`` (line 471).

    Java cases:
      * ``"true { 2 1 add } { 2 1 sub } ifelse"`` → pops 3.
      * ``"false { 2 1 add } { 2 1 sub } ifelse"`` → pops 1.
    """
    # true → first procedure (add) runs
    ctx = _ctx()
    ctx.get_stack().extend([True, _proc_2_1_add(), _proc_2_1_sub()])
    IfElse().execute(ctx)
    assert ctx.get_stack() == [3]

    # false → second procedure (sub) runs
    ctx = _ctx()
    ctx.get_stack().extend([False, _proc_2_1_add(), _proc_2_1_sub()])
    IfElse().execute(ctx)
    assert ctx.get_stack() == [1]
