"""Bitwise / logical PostScript operators for Type 4 functions.

Mirrors ``org.apache.pdfbox.pdmodel.common.function.type4.BitwiseOperators``
(upstream Java file 197 lines). Each inner class becomes a top-level class
here so the package layout reads as one file per operator group, the way
upstream ``BitwiseOperators.java`` reads as one file with seven static inner
classes plus an abstract logical base.

The runtime implementations of these operators are also exposed as module-level
functions in :mod:`pypdfbox.pdmodel.common.function.pd_function_type4` (e.g.
``_op_and``, ``_op_bitshift``); those are what the parser-driven dispatcher
actually calls today. The class shapes here exist so callers that walk the
upstream OOP API (``new BitwiseOperators.And()`` style) have something to bind
to via the ``Operators`` registry. Both layers must stay behaviourally
equivalent — touch the ``_op_*`` helpers and these classes together.

Java's ``True`` / ``False`` inner classes are renamed ``TrueFunc`` /
``FalseFunc`` because ``True`` / ``False`` are Python keywords. The PostScript
operator names registered via :class:`Operators` remain ``"true"`` / ``"false"``.
"""

from __future__ import annotations

from abc import abstractmethod

# Import ``Operator`` and ``ExecutionContext`` directly from leaf modules
# rather than the package root — the package ``__init__.py`` re-exports the
# same names but also pulls in ``instruction_sequence`` / ``operators`` /
# ``parser`` which other Wave 1277 agents own. Importing the leaf modules
# keeps this file usable even when those parallel-landing modules haven't
# merged yet.
from .execution_context import ExecutionContext
from .operator import Operator

# ---- abstract logical base -----------------------------------------------


class AbstractLogicalOperator(Operator):
    """Abstract base for two-operand logical operators (``and``/``or``/``xor``).

    Mirrors ``BitwiseOperators.AbstractLogicalOperator`` (upstream Java lines
    33-67). Pops two operands, dispatches to :meth:`apply_for_boolean` for
    ``bool``/``bool`` operands and :meth:`apply_for_integer` for ``int``/``int``
    operands. Mixed types raise :class:`TypeError` (Python's equivalent of
    upstream ``ClassCastException``).
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        op2 = stack.pop()
        op1 = stack.pop()
        # ``isinstance(x, bool)`` must be checked before ``int`` because
        # ``bool`` is a subclass of ``int`` in Python; the bool/bool branch
        # has to win for upstream parity (matches Java ``instanceof Boolean``).
        if isinstance(op1, bool) and isinstance(op2, bool):
            stack.append(self.apply_for_boolean(op1, op2))
        elif (
            isinstance(op1, int)
            and not isinstance(op1, bool)
            and isinstance(op2, int)
            and not isinstance(op2, bool)
        ):
            stack.append(self.apply_for_integer(op1, op2))
        else:
            raise TypeError("Operands must be bool/bool or int/int")

    @abstractmethod
    def apply_for_boolean(self, bool1: bool, bool2: bool) -> bool:
        """Apply the operator to two boolean operands."""

    @abstractmethod
    def apply_for_integer(self, int1: int, int2: int) -> int:
        """Apply the operator to two integer operands."""

    def applyfor_integer(self, int1: int, int2: int) -> int:
        """Upstream-named alias for :meth:`apply_for_integer`.

        Upstream Java has a typo: ``applyforInteger`` (lowercase ``f``)
        rather than ``applyForInteger``. The exact upstream snake-case
        mapping is preserved as an alias so the parity scanner sees the
        method name from upstream PDFBox 3.0.x.
        """
        return self.apply_for_integer(int1, int2)


# ---- And / Or / Xor -------------------------------------------------------


class And(AbstractLogicalOperator):
    """Implements the ``and`` operator.

    Mirrors ``BitwiseOperators.And`` (upstream Java lines 69-84).
    """

    def apply_for_boolean(self, bool1: bool, bool2: bool) -> bool:
        return bool1 and bool2

    def apply_for_integer(self, int1: int, int2: int) -> int:
        return int1 & int2


class Or(AbstractLogicalOperator):
    """Implements the ``or`` operator.

    Mirrors ``BitwiseOperators.Or`` (upstream Java lines 149-165).
    """

    def apply_for_boolean(self, bool1: bool, bool2: bool) -> bool:
        return bool1 or bool2

    def apply_for_integer(self, int1: int, int2: int) -> int:
        return int1 | int2


class Xor(AbstractLogicalOperator):
    """Implements the ``xor`` operator.

    Mirrors ``BitwiseOperators.Xor`` (upstream Java lines 179-195).
    """

    def apply_for_boolean(self, bool1: bool, bool2: bool) -> bool:
        return bool1 ^ bool2

    def apply_for_integer(self, int1: int, int2: int) -> int:
        return int1 ^ int2


# ---- Bitshift -------------------------------------------------------------


class Bitshift(Operator):
    """Implements the ``bitshift`` operator.

    Mirrors ``BitwiseOperators.Bitshift`` (upstream Java lines 86-107).
    Pops a shift count (top) and an int value, pushes ``value << shift`` for
    a non-negative shift, ``value >> abs(shift)`` for a negative shift.
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        shift = stack.pop()
        int1 = stack.pop()
        if not isinstance(shift, int) or isinstance(shift, bool):
            raise TypeError("bitshift: shift count must be int")
        if not isinstance(int1, int) or isinstance(int1, bool):
            raise TypeError("bitshift: value must be int")
        if shift < 0:
            stack.append(int1 >> abs(shift))
        else:
            stack.append(int1 << shift)


# ---- Not ------------------------------------------------------------------


class Not(Operator):
    """Implements the ``not`` operator.

    Mirrors ``BitwiseOperators.Not`` (upstream Java lines 121-147). On a
    boolean operand, returns logical negation. On an integer operand, returns
    arithmetic negation (``-int1``) — *not* bitwise complement. This is the
    upstream PDFBox 3.0 behaviour; see the comment on
    :func:`pypdfbox.pdmodel.common.function.pd_function_type4._op_not` for the
    full rationale (parity with PDFBox wins over the PostScript Reference).
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        op1 = stack.pop()
        if isinstance(op1, bool):
            stack.append(not op1)
        elif isinstance(op1, int):
            stack.append(-op1)
        else:
            raise TypeError("Operand must be bool or int")


# ---- TrueFunc / FalseFunc -------------------------------------------------


class TrueFunc(Operator):
    """Implements the ``true`` operator.

    Mirrors ``BitwiseOperators.True`` (upstream Java lines 167-177). Renamed
    from upstream ``True`` because ``True`` is a reserved keyword in Python;
    the PostScript operator name registered against this class remains
    ``"true"``. Pushes :data:`True` onto the stack.
    """

    def execute(self, context: ExecutionContext) -> None:
        context.get_stack().append(True)


class FalseFunc(Operator):
    """Implements the ``false`` operator.

    Mirrors ``BitwiseOperators.False`` (upstream Java lines 109-119). Renamed
    from upstream ``False`` because ``False`` is a reserved keyword in Python;
    the PostScript operator name registered against this class remains
    ``"false"``. Pushes :data:`False` onto the stack.
    """

    def execute(self, context: ExecutionContext) -> None:
        context.get_stack().append(False)


__all__ = [
    "And",
    "Bitshift",
    "FalseFunc",
    "Not",
    "Or",
    "TrueFunc",
    "Xor",
]
