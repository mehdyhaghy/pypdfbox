"""Execution context for Type 4 (PostScript calculator) functions.

Mirrors upstream
``org.apache.pdfbox.pdmodel.common.function.type4.ExecutionContext``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .operators import Operators


class ExecutionContext:
    """Makes up the execution context, holding the available operators
    and the execution stack.

    The stack is a plain Python ``list`` (used as a LIFO stack); upstream
    uses ``java.util.Stack``.
    """

    def __init__(self, operator_set: Operators) -> None:
        """Create a new execution context.

        :param operator_set: the operator set to use
        """
        self._operators = operator_set
        self._stack: list[object] = []

    def get_stack(self) -> list[object]:
        """Return the stack used by this execution context.

        Mirrors upstream ``getStack()``. The returned list is mutable and
        is the live stack; callers can ``append``/``pop`` directly.
        """
        return self._stack

    def get_operators(self) -> Operators:
        """Return the operator set used by this execution context.

        Mirrors upstream ``getOperators()``.
        """
        return self._operators

    def pop_number(self) -> int | float:
        """Pop a number (int or real) from the stack.

        Mirrors upstream ``popNumber()`` — raises ``TypeError`` (Python's
        equivalent of ``ClassCastException``) when the popped value is
        neither ``int`` nor ``float``. Booleans (which are technically
        ``int`` subclasses in Python) are explicitly rejected.
        """
        value = self._stack.pop()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"expected number on stack, got {type(value).__name__}"
            )
        return value

    def pop_int(self) -> int:
        """Pop a value of type ``int`` from the stack.

        Mirrors upstream ``popInt()`` — raises ``TypeError`` when the
        popped value is not an ``int``. Booleans (``int`` subclasses in
        Python) are rejected to match the Java semantics where
        ``Boolean`` cannot cast to ``Integer``.
        """
        value = self._stack.pop()
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"expected int on stack, got {type(value).__name__}"
            )
        return value

    def pop_real(self) -> float:
        """Pop a number from the stack and return it as a real value.

        Mirrors upstream ``popReal()`` — raises ``TypeError`` when the
        popped value is not numeric. Integers are widened to ``float``
        (mirrors Java ``Number.floatValue()``).
        """
        value = self._stack.pop()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"expected number on stack, got {type(value).__name__}"
            )
        return float(value)


__all__ = ["ExecutionContext"]
