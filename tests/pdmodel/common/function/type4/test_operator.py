"""Hand-written tests for the abstract :class:`Operator` base.

The class itself is purely an interface (single abstract method); we
exercise the contract — instantiation refused, subclasses must
implement ``execute``.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4 import (
    ExecutionContext,
    Operator,
    Operators,
)


def test_operator_is_abstract() -> None:
    """The base class cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Operator()  # type: ignore[abstract]


def test_subclass_must_implement_execute() -> None:
    """A subclass that does not override ``execute`` is still abstract."""

    class Incomplete(Operator):  # type: ignore[abstract]
        pass

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_concrete_subclass_runs() -> None:
    """A concrete subclass can be invoked via ``execute(context)``."""
    seen: list[int] = []

    class Push42(Operator):
        def execute(self, context: ExecutionContext) -> None:
            context.get_stack().append(42)
            seen.append(1)

    op = Push42()
    ctx = ExecutionContext(Operators())
    op.execute(ctx)
    assert ctx.get_stack() == [42]
    assert seen == [1]
