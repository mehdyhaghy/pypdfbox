"""Conditional PostScript operators (``if`` / ``ifelse``) for Type 4 functions.

Mirrors ``org.apache.pdfbox.pdmodel.common.function.type4.ConditionalOperators``
(upstream Java file 72 lines). Each inner class becomes a top-level class here
so the package layout reads as one file per operator group, the way upstream
``ConditionalOperators.java`` reads as one file with two static inner classes.

The runtime implementations of these operators are also exposed as module-level
functions in :mod:`pypdfbox.pdmodel.common.function.pd_function_type4` (e.g.
``_op_if``, ``_op_ifelse``); those are what the parser-driven dispatcher
actually calls today. The class shapes here exist so callers that walk the
upstream OOP API (``new ConditionalOperators.IfElse()`` style) have something
to bind to via the ``Operators`` registry. Both layers must stay
behaviourally equivalent — touch the ``_op_if`` / ``_op_ifelse`` helpers and
these classes together.

A "procedure" on the stack is an
:class:`pypdfbox.pdmodel.common.function.type4.InstructionSequence` (mirrors
the upstream type). Anything else raises :class:`TypeError` (Python's
equivalent of upstream ``ClassCastException``).
"""

from __future__ import annotations

# Import ``Operator`` and ``ExecutionContext`` directly from leaf modules
# rather than the package root — same rationale as
# :mod:`bitwise_operators` (some sibling modules land in parallel waves).
from .execution_context import ExecutionContext
from .instruction_sequence import InstructionSequence
from .operator import Operator


class If(Operator):
    """Implements the ``if`` operator.

    Mirrors ``ConditionalOperators.If`` (upstream Java lines 33-48). Pops a
    procedure (top) and a boolean condition; if the condition is :data:`True`,
    executes the procedure against ``context``. Otherwise the procedure is
    discarded silently — same as upstream.
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        proc = stack.pop()
        condition = stack.pop()
        if not isinstance(proc, InstructionSequence):
            raise TypeError("if: top of stack must be an InstructionSequence")
        if not isinstance(condition, bool):
            raise TypeError("if: condition must be a boolean")
        if condition:
            proc.execute(context)


class IfElse(Operator):
    """Implements the ``ifelse`` operator.

    Mirrors ``ConditionalOperators.IfElse`` (upstream Java lines 50-70). Pops
    a "false" procedure (top), a "true" procedure, and a boolean condition;
    executes the matching procedure against ``context`` and discards the other.
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        proc2 = stack.pop()
        proc1 = stack.pop()
        condition = stack.pop()
        if not isinstance(proc1, InstructionSequence) or not isinstance(
            proc2, InstructionSequence
        ):
            raise TypeError("ifelse: both procedures must be InstructionSequence")
        if not isinstance(condition, bool):
            raise TypeError("ifelse: condition must be a boolean")
        if condition:
            proc1.execute(context)
        else:
            proc2.execute(context)


__all__ = ["If", "IfElse"]
