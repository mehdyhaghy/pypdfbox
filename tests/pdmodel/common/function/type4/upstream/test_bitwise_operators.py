"""Upstream-shaped tests ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestOperators.java``
(``testAnd``, ``testBitshift``, ``testNot``, ``testOr``, ``testXor``).

The Java tests drive ``InstructionSequenceBuilder.parse(...)`` and then check
each ``pop()`` in reverse order (LIFO). We exercise the same operand sequences
directly through the operator classes; the assertions match the Java pop order
(top of stack popped first).

``testTrue`` / ``testFalse`` are not present in upstream ``TestOperators.java``
(no dedicated cases — the literals are exercised indirectly via ``testAnd`` /
``testOr``). We add explicit one-line cases below for completeness.
"""

from __future__ import annotations

from pypdfbox.pdmodel.common.function.type4.bitwise_operators import (
    And,
    Bitshift,
    FalseFunc,
    Not,
    Or,
    TrueFunc,
    Xor,
)
from pypdfbox.pdmodel.common.function.type4.execution_context import (
    ExecutionContext,
)


class _StubOperators:
    pass


def _run(op_cls: type, *operands: object) -> object:
    ctx = ExecutionContext(_StubOperators())
    ctx.get_stack().extend(operands)
    op_cls().execute(ctx)
    stack = ctx.get_stack()
    assert len(stack) == 1, f"expected one result, got {stack!r}"
    return stack[0]


def test_and() -> None:
    """Ported from ``TestOperators.testAnd`` (line 70).

    Java program: ``"true true and true false and"`` → pops False, True.
    Java program: ``"99 1 and 52 7 and"`` → pops 4, 1.
    """
    # bool/bool
    assert _run(And, True, True) is True
    assert _run(And, True, False) is False
    # int/int
    assert _run(And, 99, 1) == 1
    assert _run(And, 52, 7) == 4


def test_bitshift() -> None:
    """Ported from ``TestOperators.testBitshift`` (line 336).

    Java program: ``"7 3 bitshift 142 -3 bitshift"`` → pops 17, 56.
    """
    assert _run(Bitshift, 7, 3) == 56
    assert _run(Bitshift, 142, -3) == 17


def test_not() -> None:
    """Ported from ``TestOperators.testNot`` (line 413).

    Java program: ``"true not false not"`` → pops True, False.
    Java program: ``"52 not -37 not"`` → pops 37, -52.
    """
    assert _run(Not, True) is False
    assert _run(Not, False) is True
    assert _run(Not, 52) == -52
    assert _run(Not, -37) == 37


def test_or() -> None:
    """Ported from ``TestOperators.testOr`` (line 427).

    Java program: ``"true true or true false or false false or"``
        → pops False, True, True.
    Java program: ``"17 5 or 1 1 or"`` → pops 1, 21.
    """
    assert _run(Or, True, True) is True
    assert _run(Or, True, False) is True
    assert _run(Or, False, False) is False
    assert _run(Or, 17, 5) == 21
    assert _run(Or, 1, 1) == 1


def test_xor() -> None:
    """Ported from ``TestOperators.testXor`` (line 441).

    Java program: ``"true true xor true false xor false false xor"``
        → pops False, True, False.
    Java program: ``"7 3 xor 12 3 or"`` (note: the upstream test mixes ``or``
    in here; we cover the ``xor`` portion).
    """
    assert _run(Xor, True, True) is False
    assert _run(Xor, True, False) is True
    assert _run(Xor, False, False) is False
    # 7 ^ 3 = 4
    assert _run(Xor, 7, 3) == 4


def test_true() -> None:
    """No dedicated upstream case; ``true`` literal is exercised by testAnd.

    Direct check: ``TrueFunc`` pushes :data:`True`.
    """
    ctx = ExecutionContext(_StubOperators())
    TrueFunc().execute(ctx)
    assert ctx.get_stack() == [True]


def test_false() -> None:
    """No dedicated upstream case; ``false`` literal is exercised by testOr.

    Direct check: ``FalseFunc`` pushes :data:`False`.
    """
    ctx = ExecutionContext(_StubOperators())
    FalseFunc().execute(ctx)
    assert ctx.get_stack() == [False]
