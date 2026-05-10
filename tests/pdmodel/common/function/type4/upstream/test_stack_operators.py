"""Stack-operator tests ported from upstream PDFBox 3.0
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestOperators.java``
(testCopy / testDup / testExch / testIndex / testPop / testRoll, lines
~480-561).

Upstream drives the operators through ``Type4Tester`` which builds a full
parser + executor pipeline. We translate to direct class-shape execution
against an ``ExecutionContext`` populated by hand, since this test file is
the upstream-shaped per-class parity check; the executor-level parity
already lives in ``tests/pdmodel/common/function/upstream/test_pd_function_type4.py``.

PostScript stack literals in the upstream cases (``1 2 3 3 copy``) push
bottom-up; we replicate the same order via ``stack.extend([...])``.
"""

from __future__ import annotations

from pypdfbox.pdmodel.common.function.type4.stack_operators import (
    Copy,
    Dup,
    Exch,
    ExecutionContext,
    Index,
    Pop,
    Roll,
)


def _ctx_with(*items: object) -> ExecutionContext:
    try:
        ctx = ExecutionContext()
    except TypeError:
        # The canonical ExecutionContext (post-Agent-1) takes an Operators
        # registry; the stack ops only touch get_stack() so ``None`` is fine.
        ctx = ExecutionContext(None)
    ctx.get_stack().extend(items)
    return ctx


def test_copy() -> None:
    """Upstream: ``true 1 2 3 3 copy`` then pop 3,2,1,3,2,1,true to empty."""
    ctx = _ctx_with(True, 1, 2, 3, 3)
    Copy().execute(ctx)
    assert ctx.get_stack() == [True, 1, 2, 3, 1, 2, 3]


def test_dup() -> None:
    """Upstream: ``true 1 2 dup`` -> ``[true, 1, 2, 2]``; ``true dup`` -> ``[true, true]``."""
    ctx = _ctx_with(True, 1, 2)
    Dup().execute(ctx)
    assert ctx.get_stack() == [True, 1, 2, 2]

    ctx = _ctx_with(True)
    Dup().execute(ctx)
    assert ctx.get_stack() == [True, True]


def test_exch() -> None:
    """Upstream: ``true 1 exch`` -> ``[1, true]``; ``1 2.5 exch`` -> ``[2.5, 1]``."""
    ctx = _ctx_with(True, 1)
    Exch().execute(ctx)
    assert ctx.get_stack() == [1, True]

    ctx = _ctx_with(1, 2.5)
    Exch().execute(ctx)
    assert ctx.get_stack() == [2.5, 1]


def test_index() -> None:
    """Upstream: ``1 2 3 4 0 index`` -> ``[1, 2, 3, 4, 4]``;
    ``1 2 3 4 3 index`` -> ``[1, 2, 3, 4, 1]``."""
    ctx = _ctx_with(1, 2, 3, 4, 0)
    Index().execute(ctx)
    assert ctx.get_stack() == [1, 2, 3, 4, 4]

    ctx = _ctx_with(1, 2, 3, 4, 3)
    Index().execute(ctx)
    assert ctx.get_stack() == [1, 2, 3, 4, 1]


def test_pop() -> None:
    """Upstream: ``1 pop 7 2 pop`` -> ``[7]``; ``1 2 3 pop pop`` -> ``[1]``.

    ``Pop`` only knows how to discard the top element; we apply it the same
    number of times the upstream program does."""
    ctx = _ctx_with(1)
    Pop().execute(ctx)
    ctx.get_stack().extend([7, 2])
    Pop().execute(ctx)
    assert ctx.get_stack() == [7]

    ctx = _ctx_with(1, 2, 3)
    Pop().execute(ctx)
    Pop().execute(ctx)
    assert ctx.get_stack() == [1]


def test_roll() -> None:
    """Upstream: ``1 2 3 4 5 5 -2 roll`` -> ``[3, 4, 5, 1, 2]``;
    ``1 2 3 4 5 5 2 roll`` -> ``[4, 5, 1, 2, 3]``;
    ``1 2 3 3 0 roll`` -> ``[1, 2, 3]``."""
    ctx = _ctx_with(1, 2, 3, 4, 5, 5, -2)
    Roll().execute(ctx)
    assert ctx.get_stack() == [3, 4, 5, 1, 2]

    ctx = _ctx_with(1, 2, 3, 4, 5, 5, 2)
    Roll().execute(ctx)
    assert ctx.get_stack() == [4, 5, 1, 2, 3]

    ctx = _ctx_with(1, 2, 3, 3, 0)
    Roll().execute(ctx)
    assert ctx.get_stack() == [1, 2, 3]
