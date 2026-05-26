"""Hand-written tests for the :class:`Operators` registry."""

from __future__ import annotations

from pypdfbox.pdmodel.common.function.type4 import (
    ExecutionContext,
    InstructionSequenceBuilder,
    Operator,
    Operators,
)


def test_get_operator_returns_operator_instance() -> None:
    ops = Operators()
    op = ops.get_operator("add")
    assert isinstance(op, Operator)


def test_get_operator_unknown_returns_none() -> None:
    ops = Operators()
    assert ops.get_operator("not_a_real_op") is None


def test_registered_operator_names() -> None:
    """Mirrors the 42 entries upstream registers (21 arithmetic, 13
    bitwise/relational, 2 conditional, 6 stack)."""
    ops = Operators()
    expected = {
        # arithmetic (21)
        "add", "abs", "atan", "ceiling", "cos", "cvi", "cvr", "div", "exp",
        "floor", "idiv", "ln", "log", "mod", "mul", "neg", "round", "sin",
        "sqrt", "sub", "truncate",
        # bitwise (7) + relational (6) = 13
        "and", "bitshift", "false", "not", "or", "true", "xor",
        "eq", "ge", "gt", "le", "lt", "ne",
        # conditional (2)
        "if", "ifelse",
        # stack (6)
        "copy", "dup", "exch", "index", "pop", "roll",
    }
    for name in expected:
        assert ops.get_operator(name) is not None, f"missing operator: {name}"


def test_count_matches_upstream() -> None:
    """Upstream pre-sizes the HashMap to 42 entries."""
    ops = Operators()
    # Internal map is _operators; size matches upstream.
    assert len(ops._operators) == 42  # noqa: SLF001


def test_if_dispatches_proc() -> None:
    """End-to-end: an ``if`` lookup resolves to a real Operator that
    can run a nested InstructionSequence."""
    seq = InstructionSequenceBuilder.parse("true { 99 } if")
    ctx = ExecutionContext(Operators())
    seq.execute(ctx)
    assert ctx.get_stack() == [99]


def test_ifelse_dispatches_proc() -> None:
    seq = InstructionSequenceBuilder.parse("false { 1 } { 2 } ifelse")
    ctx = ExecutionContext(Operators())
    seq.execute(ctx)
    assert ctx.get_stack() == [2]


def test_true_false_resolve_to_dedicated_classes() -> None:
    """``true`` / ``false`` must resolve to the dedicated
    :class:`TrueFunc` / :class:`FalseFunc` operator classes (upstream
    ``BitwiseOperators.True`` / ``.False``, renamed because ``True`` /
    ``False`` are Python keywords) — not the internal legacy fallback
    adapter. Guards the registry's class-name map, which previously
    pointed at the non-existent names ``"True"`` / ``"False"`` and
    silently degraded to ``_LegacyOperatorAdapter``."""
    from pypdfbox.pdmodel.common.function.type4.bitwise_operators import (
        FalseFunc,
        TrueFunc,
    )

    ops = Operators()
    assert isinstance(ops.get_operator("true"), TrueFunc)
    assert isinstance(ops.get_operator("false"), FalseFunc)


def test_true_false_push_booleans() -> None:
    """End-to-end: the resolved operators push the right values."""
    ctx = ExecutionContext(Operators())
    ops = Operators()
    ops.get_operator("true").execute(ctx)
    ops.get_operator("false").execute(ctx)
    assert ctx.get_stack() == [True, False]


def test_each_operator_is_independent_instance() -> None:
    """The registry stores one instance per name; the same name across
    two ``Operators`` instances need not be the same Python object."""
    ops_a = Operators()
    ops_b = Operators()
    assert ops_a.get_operator("add") is not None
    assert ops_b.get_operator("add") is not None
    # Independent registries — neither shares state with the other.
    assert ops_a is not ops_b
