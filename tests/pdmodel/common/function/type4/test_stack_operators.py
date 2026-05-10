"""Tests for the Type 4 stack operator class shapes.

Hand-written coverage for every concrete subclass of ``Operator`` ported
from upstream ``StackOperators.java``. Companion JUnit cases live in
``tests/pdmodel/common/function/upstream/test_pd_function_type4.py``
(via the executor) and in
``tests/pdmodel/common/function/type4/upstream/test_stack_operators.py``
(direct class-shaped translation of upstream's ``TestOperators``
testCopy / testDup / testExch / testIndex / testPop / testRoll cases).
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4.stack_operators import (
    Copy,
    Dup,
    Exch,
    ExecutionContext,
    Index,
    Operator,
    Pop,
    Roll,
)


def _ctx() -> ExecutionContext:
    """Build an empty ``ExecutionContext``.

    The upstream constructor takes an ``Operators`` registry; the stack
    operator classes only ever touch ``get_stack()``, so passing ``None``
    is sufficient and avoids a hard dependency on the registry being
    landed by Agent 1. The local fallback path uses a no-arg constructor;
    we try that first.
    """
    try:
        return ExecutionContext()
    except TypeError:
        return ExecutionContext(None)


# --------------------------------------------------------------------------
# Class-shape sanity
# --------------------------------------------------------------------------


def test_all_operators_subclass_operator() -> None:
    for cls in (Copy, Dup, Exch, Index, Pop, Roll):
        assert issubclass(cls, Operator), cls
        # Each class is concretely instantiable (no abstract methods left).
        instance = cls()
        assert isinstance(instance, Operator)


# --------------------------------------------------------------------------
# Copy
# --------------------------------------------------------------------------


def test_copy_three_from_top() -> None:
    """Mirrors upstream ``testCopy``: ``true 1 2 3 3 copy`` -> stack
    ``[true, 1, 2, 3, 1, 2, 3]`` (bottom-up)."""
    ctx = _ctx()
    ctx.get_stack().extend([True, 1, 2, 3, 3])
    Copy().execute(ctx)
    assert ctx.get_stack() == [True, 1, 2, 3, 1, 2, 3]


def test_copy_zero_is_noop() -> None:
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, 0])
    Copy().execute(ctx)
    assert ctx.get_stack() == [1, 2]


def test_copy_negative_is_silent_per_upstream() -> None:
    """Upstream guards on ``n > 0`` and silently does nothing for ``n <= 0``;
    we mirror that to preserve behavioural parity."""
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, -1])
    Copy().execute(ctx)
    assert ctx.get_stack() == [1, 2]


# --------------------------------------------------------------------------
# Dup
# --------------------------------------------------------------------------


def test_dup_top() -> None:
    ctx = _ctx()
    ctx.get_stack().extend([True, 1, 2])
    Dup().execute(ctx)
    assert ctx.get_stack() == [True, 1, 2, 2]


def test_dup_singleton_bool() -> None:
    """Mirrors upstream ``testDup`` second case: ``true dup`` -> ``true true``."""
    ctx = _ctx()
    ctx.get_stack().append(True)
    Dup().execute(ctx)
    assert ctx.get_stack() == [True, True]


def test_dup_empty_raises() -> None:
    ctx = _ctx()
    with pytest.raises(IndexError):
        Dup().execute(ctx)


# --------------------------------------------------------------------------
# Exch
# --------------------------------------------------------------------------


def test_exch_swaps_top_two() -> None:
    """Mirrors upstream ``testExch``: ``true 1 exch`` -> ``[1, true]``."""
    ctx = _ctx()
    ctx.get_stack().extend([True, 1])
    Exch().execute(ctx)
    assert ctx.get_stack() == [1, True]


def test_exch_mixed_numeric() -> None:
    ctx = _ctx()
    ctx.get_stack().extend([1, 2.5])
    Exch().execute(ctx)
    assert ctx.get_stack() == [2.5, 1]


# --------------------------------------------------------------------------
# Index
# --------------------------------------------------------------------------


def test_index_zero_is_dup_top() -> None:
    """Mirrors upstream ``testIndex`` first case: ``1 2 3 4 0 index`` -> top
    becomes ``4 4`` so the bottom-up stack is ``[1, 2, 3, 4, 4]``."""
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, 3, 4, 0])
    Index().execute(ctx)
    assert ctx.get_stack() == [1, 2, 3, 4, 4]


def test_index_three_picks_bottom_of_top_four() -> None:
    """Mirrors upstream second case: ``1 2 3 4 3 index`` pushes element 3
    below the (post-pop) top, i.e. ``1`` -> ``[1, 2, 3, 4, 1]``."""
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, 3, 4, 3])
    Index().execute(ctx)
    assert ctx.get_stack() == [1, 2, 3, 4, 1]


def test_index_negative_raises() -> None:
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, -1])
    with pytest.raises(ValueError, match="rangecheck"):
        Index().execute(ctx)


# --------------------------------------------------------------------------
# Pop
# --------------------------------------------------------------------------


def test_pop_discards_top() -> None:
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, 3])
    Pop().execute(ctx)
    assert ctx.get_stack() == [1, 2]


def test_pop_empty_raises() -> None:
    ctx = _ctx()
    with pytest.raises(IndexError):
        Pop().execute(ctx)


# --------------------------------------------------------------------------
# Roll
# --------------------------------------------------------------------------


def test_roll_negative_two() -> None:
    """Mirrors upstream ``testRoll`` first case: ``1 2 3 4 5 5 -2 roll``
    rolls top-5 by -2 -> bottom-up ``[3, 4, 5, 1, 2]``."""
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, 3, 4, 5, 5, -2])
    Roll().execute(ctx)
    assert ctx.get_stack() == [3, 4, 5, 1, 2]


def test_roll_positive_two() -> None:
    """Mirrors upstream second case: ``1 2 3 4 5 5 2 roll`` -> ``[4, 5, 1, 2, 3]``."""
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, 3, 4, 5, 5, 2])
    Roll().execute(ctx)
    assert ctx.get_stack() == [4, 5, 1, 2, 3]


def test_roll_zero_j_is_noop() -> None:
    """Mirrors upstream third case: ``1 2 3 3 0 roll`` -> ``[1, 2, 3]``."""
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, 3, 3, 0])
    Roll().execute(ctx)
    assert ctx.get_stack() == [1, 2, 3]


def test_roll_negative_n_raises() -> None:
    ctx = _ctx()
    ctx.get_stack().extend([1, 2, -1, 1])
    with pytest.raises(ValueError, match="rangecheck"):
        Roll().execute(ctx)
