"""Coverage round-out for ``pypdfbox.pdmodel.common.function.type4.operator``.

Re-exercises the abstract :class:`Operator` interface, including the
explicit ``NotImplementedError`` body of the abstract :meth:`execute`
method (reached by an opt-out subclass that defers to ``super``), and
the dispatch path via concrete subclasses.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4 import (
    ExecutionContext,
    Operator,
    Operators,
)


def test_operator_class_cannot_be_instantiated_directly() -> None:
    """``Operator`` is abstract — direct instantiation raises ``TypeError``."""
    with pytest.raises(TypeError):
        Operator()  # type: ignore[abstract]


def test_subclass_without_execute_remains_abstract() -> None:
    """A subclass that fails to implement ``execute`` is still abstract."""

    class _StillAbstract(Operator):  # type: ignore[abstract]
        pass

    with pytest.raises(TypeError):
        _StillAbstract()  # type: ignore[abstract]


def test_explicit_super_execute_raises_not_implemented() -> None:
    """A concrete subclass that calls ``super().execute`` reaches the
    abstract body which raises ``NotImplementedError``. Covers the
    ``raise NotImplementedError`` line in :meth:`Operator.execute`."""

    class _CallsSuper(Operator):
        def execute(self, context: ExecutionContext) -> None:
            super().execute(context)

    op = _CallsSuper()
    ctx = ExecutionContext(Operators())
    with pytest.raises(NotImplementedError):
        op.execute(ctx)


def test_concrete_subclass_can_mutate_execution_stack() -> None:
    """Happy path: a concrete subclass receives the context and can
    inspect / mutate the stack."""

    class _PushSeven(Operator):
        def execute(self, context: ExecutionContext) -> None:
            context.get_stack().append(7)

    op = _PushSeven()
    ctx = ExecutionContext(Operators())
    op.execute(ctx)
    assert ctx.get_stack() == [7]


def test_multiple_subclasses_have_independent_execute() -> None:
    """Two concrete subclasses dispatched on the same context produce
    distinct side-effects — confirms there is no shared instance state
    on the abstract base."""

    class _PushA(Operator):
        def execute(self, context: ExecutionContext) -> None:
            context.get_stack().append("A")

    class _PushB(Operator):
        def execute(self, context: ExecutionContext) -> None:
            context.get_stack().append("B")

    ctx = ExecutionContext(Operators())
    _PushA().execute(ctx)
    _PushB().execute(ctx)
    assert ctx.get_stack() == ["A", "B"]


def test_operator_subclass_can_pop_and_re_push() -> None:
    """End-to-end through the abstract interface using
    ``ExecutionContext.pop_int``."""

    class _Increment(Operator):
        def execute(self, context: ExecutionContext) -> None:
            value = context.pop_int()
            context.get_stack().append(value + 1)

    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(41)
    _Increment().execute(ctx)
    assert ctx.get_stack() == [42]


def test_operator_is_abstract_base_class() -> None:
    """``Operator`` inherits from ``abc.ABC`` and ``execute`` is marked
    abstract — the metaclass enforces the abstract contract."""
    import abc

    assert isinstance(Operator, abc.ABCMeta)
    # The set is exposed on the class by ``ABCMeta``.
    assert "execute" in Operator.__abstractmethods__
