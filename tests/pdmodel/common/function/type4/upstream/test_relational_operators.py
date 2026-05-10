"""Upstream-shaped tests ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestOperators.java``
(``testEq``, ``testGe``, ``testGt``, ``testLe``, ``testLt``, ``testNe``).

The Java tests drive ``InstructionSequenceBuilder.parse(...)`` and then check
each pop() in reverse order (LIFO). Until the parser/instruction-sequence
modules land we exercise the same operand sequences directly through the
operator classes; the assertions match the Java pop order.
"""

from __future__ import annotations

from pypdfbox.pdmodel.common.function.type4.execution_context import (
    ExecutionContext,
)
from pypdfbox.pdmodel.common.function.type4.relational_operators import (
    Eq,
    Ge,
    Gt,
    Le,
    Lt,
    Ne,
)


class _StubOperators:
    pass


def _run(op_cls: type, a: object, b: object) -> object:
    ctx = ExecutionContext(_StubOperators())
    ctx.get_stack().extend([a, b])
    op_cls().execute(ctx)
    stack = ctx.get_stack()
    assert len(stack) == 1, f"expected one result, got {stack!r}"
    return stack[0]


def test_eq() -> None:
    """Ported from ``TestOperators.testEq`` (line 347).

    Java program: ``"7 7 eq 7 6 eq 7 -7 eq true true eq false true eq 7.7 7.7 eq"``
    Expected pops (top→bottom): True, False, True, False, False, True.
    """
    assert _run(Eq, 7, 7) is True
    assert _run(Eq, 7, 6) is False
    assert _run(Eq, 7, -7) is False
    assert _run(Eq, True, True) is True
    assert _run(Eq, False, True) is False
    assert _run(Eq, 7.7, 7.7) is True


def test_ge() -> None:
    """Ported from ``TestOperators.testGe`` (line 358).

    Java program: ``"5 7 ge 7 5 ge 7 7 ge -1 2 ge"``
    Expected pops (top→bottom): False, True, True, False.
    """
    assert _run(Ge, 5, 7) is False
    assert _run(Ge, 7, 5) is True
    assert _run(Ge, 7, 7) is True
    assert _run(Ge, -1, 2) is False


def test_gt() -> None:
    """Ported from ``TestOperators.testGt`` (line 369).

    Java program: ``"5 7 gt 7 5 gt 7 7 gt -1 2 gt"``
    Expected pops (top→bottom): False, False, True, False.
    """
    assert _run(Gt, 5, 7) is False
    assert _run(Gt, 7, 5) is True
    assert _run(Gt, 7, 7) is False
    assert _run(Gt, -1, 2) is False


def test_le() -> None:
    """Ported from ``TestOperators.testLe`` (line 380).

    Java program: ``"5 7 le 7 5 le 7 7 le -1 2 le"``
    Expected pops (top→bottom): True, True, False, True.
    """
    assert _run(Le, 5, 7) is True
    assert _run(Le, 7, 5) is False
    assert _run(Le, 7, 7) is True
    assert _run(Le, -1, 2) is True


def test_lt() -> None:
    """Ported from ``TestOperators.testLt`` (line 391).

    Java program: ``"5 7 lt 7 5 lt 7 7 lt -1 2 lt"``
    Expected pops (top→bottom): True, False, False, True.
    """
    assert _run(Lt, 5, 7) is True
    assert _run(Lt, 7, 5) is False
    assert _run(Lt, 7, 7) is False
    assert _run(Lt, -1, 2) is True


def test_ne() -> None:
    """Ported from ``TestOperators.testNe`` (line 402).

    Java program: ``"7 7 ne 7 6 ne 7 -7 ne true true ne false true ne 7.7 7.7 ne"``
    Expected pops (top→bottom): False, True, False, True, True, False.
    """
    assert _run(Ne, 7, 7) is False
    assert _run(Ne, 7, 6) is True
    assert _run(Ne, 7, -7) is True
    assert _run(Ne, True, True) is False
    assert _run(Ne, False, True) is True
    assert _run(Ne, 7.7, 7.7) is False
