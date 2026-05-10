"""Relational PostScript operators (eq, ne, lt, le, gt, ge) for Type 4 functions.

Mirrors ``org.apache.pdfbox.pdmodel.common.function.type4.RelationalOperators``
(upstream Java file 144 lines). Each inner class becomes a top-level class here
so the package layout reads as one file per operator group, the way upstream
``RelationalOperators.java`` reads as one file with six static inner classes.

The runtime implementations of these operators are also exposed as module-level
functions in :mod:`pypdfbox.pdmodel.common.function.pd_function_type4` (e.g.
``_op_eq``); those are what the parser-driven dispatcher actually calls today.
The class shapes here exist so callers that walk the upstream OOP API
(``Operators.put("eq", new RelationalOperators.Eq())`` style) have something to
bind to once the ``Operators`` registry lands. Both layers must stay
behaviourally equivalent — touch the ``_op_*`` helpers and these classes
together.
"""

from __future__ import annotations

# Import the base ``Operator`` class and ``ExecutionContext`` directly from
# their submodules rather than from the package root — the package
# ``__init__.py`` re-exports the same names but also pulls in
# ``instruction_sequence``/``operators``/``parser`` which other Wave 1277
# agents own. Importing the leaf modules here keeps this file usable even
# when those parallel-landing modules haven't merged yet.
from .execution_context import ExecutionContext
from .operator import Operator

# ---- helpers --------------------------------------------------------------


def _is_number(value: object) -> bool:
    """Return True iff ``value`` should be treated as a PostScript number.

    Mirrors the upstream ``op instanceof Number`` check. Python ``bool`` is a
    subclass of ``int``, but in PostScript booleans are *not* numbers — so we
    explicitly exclude them, matching upstream behaviour where ``true eq 1``
    is False.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---- Eq + Ne --------------------------------------------------------------


class Eq(Operator):
    """Implements the ``eq`` operator.

    Mirrors ``RelationalOperators.Eq`` (upstream Java lines 33-62).
    Pops two operands, pushes ``True`` if they compare equal. When both
    operands are numeric the comparison is performed in float space (matches
    upstream ``Float.compare(num1.floatValue(), num2.floatValue()) == 0``).
    Otherwise falls back to Python ``==`` (mirror of Java ``op1.equals(op2)``).
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        op2 = stack.pop()
        op1 = stack.pop()
        stack.append(self.is_equal(op1, op2))

    def is_equal(self, op1: object, op2: object) -> bool:
        """Mirrors upstream ``protected boolean isEqual(Object, Object)``."""
        if _is_number(op1) and _is_number(op2):
            # Force float compare to mirror Java ``Float.compare(...)``.
            return float(op1) == float(op2)  # type: ignore[arg-type]
        return op1 == op2


class Ne(Eq):
    """Implements the ``ne`` operator.

    Mirrors ``RelationalOperators.Ne`` (upstream Java lines 131-142). Inherits
    from :class:`Eq` and inverts the equality result, exactly as upstream does.
    """

    def is_equal(self, op1: object, op2: object) -> bool:
        return not super().is_equal(op1, op2)


# ---- Numeric comparison family -------------------------------------------


class AbstractNumberComparisonOperator(Operator):
    """Mirrors private ``AbstractNumberComparisonOperator`` (upstream Java
    lines 64-81).

    Pops two operands as numbers, delegates to ``compare`` which subclasses
    override, and pushes the boolean result. Non-numeric operands raise
    ``TypeError`` — matches upstream behaviour where the cast
    ``(Number)stack.pop()`` raises ``ClassCastException``.
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        op2 = stack.pop()
        op1 = stack.pop()
        if not _is_number(op1) or not _is_number(op2):
            raise TypeError(
                "type 4 numeric comparison requires numeric operands"
            )
        stack.append(self.compare(float(op1), float(op2)))  # type: ignore[arg-type]

    def compare(self, num1: float, num2: float) -> bool:
        raise NotImplementedError


class Ge(AbstractNumberComparisonOperator):
    """Implements the ``ge`` operator.

    Mirrors ``RelationalOperators.Ge`` (upstream Java lines 83-93).
    """

    def compare(self, num1: float, num2: float) -> bool:
        return num1 >= num2


class Gt(AbstractNumberComparisonOperator):
    """Implements the ``gt`` operator.

    Mirrors ``RelationalOperators.Gt`` (upstream Java lines 95-105).
    """

    def compare(self, num1: float, num2: float) -> bool:
        return num1 > num2


class Le(AbstractNumberComparisonOperator):
    """Implements the ``le`` operator.

    Mirrors ``RelationalOperators.Le`` (upstream Java lines 107-117).
    """

    def compare(self, num1: float, num2: float) -> bool:
        return num1 <= num2


class Lt(AbstractNumberComparisonOperator):
    """Implements the ``lt`` operator.

    Mirrors ``RelationalOperators.Lt`` (upstream Java lines 119-129).
    """

    def compare(self, num1: float, num2: float) -> bool:
        return num1 < num2


__all__ = [
    "Eq",
    "ExecutionContext",
    "Ge",
    "Gt",
    "Le",
    "Lt",
    "Ne",
    "Operator",
]
