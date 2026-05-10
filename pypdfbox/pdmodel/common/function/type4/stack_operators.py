"""Stack operators (Copy, Dup, Exch, Index, Pop, Roll) for Type 4 PostScript
calculator functions.

Mirrors upstream
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/StackOperators.java``
(166 lines, six package-private inner classes implementing the ``Operator``
interface). Each class is a thin OOP shape around the corresponding
free-function implementation in ``pd_function_type4`` so callers that want
the upstream class-shaped surface (e.g. operator-set introspection, tools
that look up an operator by class) get parity. The actual stack-machine
executor in ``pd_function_type4`` continues to dispatch via its private
callable map for speed.

PostScript semantics per PDF 32000-1 §7.10.5 / PostScript Language
Reference (3rd ed., §8). Errors mirror upstream behaviour: ``Index`` and
``Roll`` raise ``IllegalArgumentException`` on a negative count in upstream
Java; we surface that as ``ValueError`` (the closest Python analogue, used
elsewhere in the port for upstream ``IllegalArgumentException``).
"""

from __future__ import annotations

from .execution_context import ExecutionContext
from .operator import Operator

# ---- operator classes -----------------------------------------------------
#
# Each class is a leaf concrete subclass of ``Operator``. The class-level
# docstring records the upstream Java line range so a ported file -> upstream
# audit is mechanical. The behaviour is intentionally re-implemented inline
# (rather than delegating to ``pd_function_type4`` private functions) so the
# class is self-contained and free of cross-module coupling — upstream's
# inner classes have the same property.


class Copy(Operator):
    """Implements the PostScript ``copy`` operator.

    Mirrors ``StackOperators.Copy`` (upstream lines 35-53). Pops integer
    ``n`` from the stack and pushes a copy of the top ``n`` elements in
    their original order. ``n == 0`` is a no-op; ``n < 0`` is upstream
    undefined-behaviour (Java pushes nothing) — we follow upstream and
    skip silently for parity.
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        n = int(stack.pop())
        if n > 0:
            size = len(stack)
            # Snapshot before extending so we don't read what we're writing
            # — upstream guards against ConcurrentModificationException with
            # an explicit ArrayList copy; ``list[:]`` slice has the same
            # safety property.
            copy = list(stack[size - n : size])
            stack.extend(copy)


class Dup(Operator):
    """Implements the PostScript ``dup`` operator.

    Mirrors ``StackOperators.Dup`` (upstream lines 55-65). Pushes a
    duplicate of the top stack element (peek + push). Upstream raises
    ``EmptyStackException`` on an empty stack; Python's ``list[-1]`` raises
    ``IndexError`` which is the natural analogue.
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        stack.append(stack[-1])


class Exch(Operator):
    """Implements the PostScript ``exch`` operator.

    Mirrors ``StackOperators.Exch`` (upstream lines 67-80). Swaps the top
    two stack elements. Upstream pops both then pushes them in the swapped
    order; we do the same so an underflow surfaces at pop time exactly
    like upstream.
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        any2 = stack.pop()
        any1 = stack.pop()
        stack.append(any2)
        stack.append(any1)


class Index(Operator):
    """Implements the PostScript ``index`` operator.

    Mirrors ``StackOperators.Index`` (upstream lines 82-98). Pops integer
    ``n`` then pushes a copy of the element ``n`` positions below the new
    top. ``n < 0`` raises ``IllegalArgumentException`` upstream; Python
    surfaces that as ``ValueError`` per the port's convention for upstream
    ``IllegalArgumentException``.
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        n = int(stack.pop())
        if n < 0:
            raise ValueError(f"rangecheck: {n}")
        size = len(stack)
        stack.append(stack[size - n - 1])


class Pop(Operator):
    """Implements the PostScript ``pop`` operator.

    Mirrors ``StackOperators.Pop`` (upstream lines 100-110). Discards the
    top stack element. Underflow surfaces as ``IndexError`` (Python's
    natural analogue of upstream ``EmptyStackException``).
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        stack.pop()


class Roll(Operator):
    """Implements the PostScript ``roll`` operator.

    Mirrors ``StackOperators.Roll`` (upstream lines 112-164). Pops integers
    ``j`` and ``n`` (``n`` deeper) and rolls the top ``n`` elements ``j``
    positions: positive ``j`` rolls toward the top, negative ``j`` rolls
    toward the bottom. ``j == 0`` is a no-op; ``n < 0`` raises
    ``ValueError`` (upstream ``IllegalArgumentException``).

    The upstream implementation hand-rolls the rotation with two
    ``LinkedList`` helpers to preserve order across pops; we follow its
    structure verbatim so behaviour is bit-exact, including the ``j``
    out-of-bounds case where upstream pops past the declared frame and
    naturally raises ``EmptyStackException`` (Python: ``IndexError``).
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        j = int(stack.pop())
        n = int(stack.pop())
        if j == 0:
            return  # Nothing to do
        if n < 0:
            raise ValueError(f"rangecheck: {n}")

        rolled: list[object] = []
        moved: list[object] = []
        if j < 0:
            # Negative roll: rotate top n by |j| toward the bottom.
            n1 = n + j
            for _ in range(n1):
                moved.insert(0, stack.pop())
            for _ in range(j, 0):
                rolled.insert(0, stack.pop())
            stack.extend(moved)
            stack.extend(rolled)
        else:
            # Positive roll: rotate top n by j toward the top.
            n1 = n - j
            for _ in range(j, 0, -1):
                rolled.insert(0, stack.pop())
            for _ in range(n1):
                moved.insert(0, stack.pop())
            stack.extend(rolled)
            stack.extend(moved)


__all__ = [
    "Copy",
    "Dup",
    "Exch",
    "ExecutionContext",
    "Index",
    "Operator",
    "Pop",
    "Roll",
]
