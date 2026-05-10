"""Tests for the bitwise / logical operator class shapes.

Mirrors the OOP layer in
``pypdfbox.pdmodel.common.function.type4.bitwise_operators`` (port of
``BitwiseOperators.java``). Behavioural coverage of the same operators via
the parser-driven dispatcher already exists in
``test_pd_function_type4_opcodes.py``; these tests pin the *class* contract
(execute manipulates the stack as upstream does, inheritance shape matches).
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4.bitwise_operators import (
    AbstractLogicalOperator,
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
from pypdfbox.pdmodel.common.function.type4.operator import Operator


class _StubOperators:
    """Placeholder operator-set object.

    ``ExecutionContext.__init__`` only stores its argument; the bitwise
    operators never call ``get_operators()`` so any object works.
    """


def _ctx(*values: object) -> ExecutionContext:
    """Build a context pre-populated with ``values`` on the stack (bottom->top)."""
    ctx = ExecutionContext(_StubOperators())
    ctx.get_stack().extend(values)
    return ctx


# ---- inheritance shape ---------------------------------------------------


def test_all_bitwise_classes_subclass_operator() -> None:
    for cls in (And, Bitshift, FalseFunc, Not, Or, TrueFunc, Xor):
        assert issubclass(cls, Operator)


def test_logical_classes_share_abstract_base() -> None:
    """Mirror upstream class hierarchy: And/Or/Xor extend AbstractLogicalOperator."""
    for cls in (And, Or, Xor):
        assert issubclass(cls, AbstractLogicalOperator)
    # Bitshift / Not / TrueFunc / FalseFunc directly implement Operator,
    # not the abstract logical base — same as upstream.
    for cls in (Bitshift, Not, TrueFunc, FalseFunc):
        assert not issubclass(cls, AbstractLogicalOperator)


# ---- And -----------------------------------------------------------------


def test_and_bool_bool_true_true_pushes_true() -> None:
    ctx = _ctx(True, True)
    And().execute(ctx)
    assert ctx.get_stack() == [True]


def test_and_bool_bool_true_false_pushes_false() -> None:
    ctx = _ctx(True, False)
    And().execute(ctx)
    assert ctx.get_stack() == [False]


def test_and_int_int_bitwise_and() -> None:
    ctx = _ctx(99, 1)
    And().execute(ctx)
    assert ctx.get_stack() == [1]
    ctx = _ctx(52, 7)
    And().execute(ctx)
    assert ctx.get_stack() == [4]


def test_and_mixed_types_raises_type_error() -> None:
    ctx = _ctx(True, 1)
    with pytest.raises(TypeError):
        And().execute(ctx)


# ---- Or ------------------------------------------------------------------


def test_or_bool_bool_combinations() -> None:
    cases = [
        ((True, True), True),
        ((True, False), True),
        ((False, False), False),
    ]
    for operands, expected in cases:
        ctx = _ctx(*operands)
        Or().execute(ctx)
        assert ctx.get_stack() == [expected]


def test_or_int_int_bitwise_or() -> None:
    ctx = _ctx(17, 5)
    Or().execute(ctx)
    assert ctx.get_stack() == [21]
    ctx = _ctx(1, 1)
    Or().execute(ctx)
    assert ctx.get_stack() == [1]


def test_or_mixed_types_raises_type_error() -> None:
    ctx = _ctx(1, True)
    with pytest.raises(TypeError):
        Or().execute(ctx)


# ---- Xor -----------------------------------------------------------------


def test_xor_bool_bool_combinations() -> None:
    cases = [
        ((True, True), False),
        ((True, False), True),
        ((False, False), False),
    ]
    for operands, expected in cases:
        ctx = _ctx(*operands)
        Xor().execute(ctx)
        assert ctx.get_stack() == [expected]


def test_xor_int_int_bitwise_xor() -> None:
    ctx = _ctx(7, 3)
    Xor().execute(ctx)
    assert ctx.get_stack() == [4]


def test_xor_mixed_types_raises_type_error() -> None:
    ctx = _ctx("nope", 1)
    with pytest.raises(TypeError):
        Xor().execute(ctx)


# ---- Bitshift ------------------------------------------------------------


def test_bitshift_positive_shift_left() -> None:
    ctx = _ctx(7, 3)
    Bitshift().execute(ctx)
    assert ctx.get_stack() == [56]


def test_bitshift_negative_shift_right() -> None:
    ctx = _ctx(142, -3)
    Bitshift().execute(ctx)
    assert ctx.get_stack() == [17]


def test_bitshift_zero_shift_is_identity() -> None:
    ctx = _ctx(99, 0)
    Bitshift().execute(ctx)
    assert ctx.get_stack() == [99]


def test_bitshift_non_int_shift_raises_type_error() -> None:
    ctx = _ctx(5, True)
    with pytest.raises(TypeError):
        Bitshift().execute(ctx)


def test_bitshift_non_int_value_raises_type_error() -> None:
    ctx = _ctx(1.5, 1)
    with pytest.raises(TypeError):
        Bitshift().execute(ctx)


# ---- Not -----------------------------------------------------------------


def test_not_bool_negates() -> None:
    ctx = _ctx(True)
    Not().execute(ctx)
    assert ctx.get_stack() == [False]
    ctx = _ctx(False)
    Not().execute(ctx)
    assert ctx.get_stack() == [True]


def test_not_int_arithmetic_negation() -> None:
    """Upstream PDFBox negates (``-int1``) rather than bit-inverting; parity wins."""
    ctx = _ctx(52)
    Not().execute(ctx)
    assert ctx.get_stack() == [-52]
    ctx = _ctx(-37)
    Not().execute(ctx)
    assert ctx.get_stack() == [37]


def test_not_other_type_raises_type_error() -> None:
    ctx = _ctx("hello")
    with pytest.raises(TypeError):
        Not().execute(ctx)


# ---- TrueFunc / FalseFunc ------------------------------------------------


def test_true_func_pushes_true() -> None:
    ctx = _ctx()
    TrueFunc().execute(ctx)
    assert ctx.get_stack() == [True]


def test_false_func_pushes_false() -> None:
    ctx = _ctx()
    FalseFunc().execute(ctx)
    assert ctx.get_stack() == [False]


def test_true_false_funcs_leave_existing_stack_intact() -> None:
    ctx = _ctx(1, 2)
    TrueFunc().execute(ctx)
    FalseFunc().execute(ctx)
    assert ctx.get_stack() == [1, 2, True, False]
