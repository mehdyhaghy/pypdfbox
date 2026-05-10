"""Hand-written tests for :class:`ExecutionContext`."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4 import (
    ExecutionContext,
    Operators,
)


def test_get_stack_starts_empty() -> None:
    ctx = ExecutionContext(Operators())
    assert ctx.get_stack() == []


def test_get_operators_returns_constructor_arg() -> None:
    ops = Operators()
    ctx = ExecutionContext(ops)
    assert ctx.get_operators() is ops


def test_pop_int_returns_int() -> None:
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(7)
    assert ctx.pop_int() == 7


def test_pop_int_rejects_float() -> None:
    """Java would throw ClassCastException casting Float→Integer; we
    raise ``TypeError`` (Python's equivalent)."""
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(1.5)
    with pytest.raises(TypeError):
        ctx.pop_int()


def test_pop_int_rejects_bool() -> None:
    """Booleans are technically ``int`` subclasses in Python, but Java
    cannot cast ``Boolean`` to ``Integer``; mirror that strict typing."""
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(True)
    with pytest.raises(TypeError):
        ctx.pop_int()


def test_pop_real_widens_int() -> None:
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(3)
    val = ctx.pop_real()
    assert val == 3.0
    assert isinstance(val, float)


def test_pop_real_returns_float() -> None:
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(2.5)
    assert ctx.pop_real() == 2.5


def test_pop_real_rejects_bool() -> None:
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(False)
    with pytest.raises(TypeError):
        ctx.pop_real()


def test_pop_number_int() -> None:
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(7)
    val = ctx.pop_number()
    assert val == 7
    assert isinstance(val, int)


def test_pop_number_float() -> None:
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(2.5)
    val = ctx.pop_number()
    assert val == 2.5
    assert isinstance(val, float)


def test_pop_number_rejects_bool() -> None:
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(True)
    with pytest.raises(TypeError):
        ctx.pop_number()


def test_stack_is_live() -> None:
    """The list returned by ``get_stack()`` is the live stack."""
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(1)
    ctx.get_stack().append(2)
    assert ctx.get_stack() == [1, 2]
