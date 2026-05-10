"""Arithmetic operator class shapes mirroring upstream
``org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators``.

Upstream nests every operator as a ``static class`` inside one
``ArithmeticOperators.java`` file (see PDFBox 3.0.x Java line refs in each
class docstring). Python prefers module-level classes, so each upstream
inner class becomes a sibling class here — the public surface (class name,
single ``execute(ExecutionContext)`` method) is preserved.

Each ``execute`` delegates to the existing module-level operator
implementations on
``pypdfbox.pdmodel.common.function.pd_function_type4`` (``_op_add``,
``_op_sub`` …). That module is the source of truth for numerical
behaviour; these classes are thin shape adapters so external callers can
plug arithmetic operators into the upstream-style registry-driven
``Operator``/``ExecutionContext`` machinery as Agent 1 (Wave 1277) ports
the registry.
"""

from __future__ import annotations

from pypdfbox.pdmodel.common.function.pd_function_type4 import (
    _op_abs,
    _op_add,
    _op_atan,
    _op_ceiling,
    _op_cos,
    _op_cvi,
    _op_cvr,
    _op_div,
    _op_exp,
    _op_floor,
    _op_idiv,
    _op_ln,
    _op_log,
    _op_mod,
    _op_mul,
    _op_neg,
    _op_round,
    _op_sin,
    _op_sqrt,
    _op_sub,
    _op_truncate,
)

from .execution_context import ExecutionContext
from .operator import Operator

# ---------- arithmetic operator classes ----------


class Abs(Operator):
    """Implements the ``abs`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Abs
    (upstream ArithmeticOperators.java lines 34-50).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_abs(context.get_stack())


class Add(Operator):
    """Implements the ``add`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Add
    (upstream ArithmeticOperators.java lines 53-79).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_add(context.get_stack())


class Atan(Operator):
    """Implements the ``atan`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Atan
    (upstream ArithmeticOperators.java lines 82-98).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_atan(context.get_stack())


class Ceiling(Operator):
    """Implements the ``ceiling`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Ceiling
    (upstream ArithmeticOperators.java lines 101-117).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_ceiling(context.get_stack())


class Cos(Operator):
    """Implements the ``cos`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Cos
    (upstream ArithmeticOperators.java lines 120-130).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_cos(context.get_stack())


class Cvi(Operator):
    """Implements the ``cvi`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Cvi
    (upstream ArithmeticOperators.java lines 133-142).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_cvi(context.get_stack())


class Cvr(Operator):
    """Implements the ``cvr`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Cvr
    (upstream ArithmeticOperators.java lines 145-154).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_cvr(context.get_stack())


class Div(Operator):
    """Implements the ``div`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Div
    (upstream ArithmeticOperators.java lines 157-167).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_div(context.get_stack())


class Exp(Operator):
    """Implements the ``exp`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Exp
    (upstream ArithmeticOperators.java lines 170-181).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_exp(context.get_stack())


class Floor(Operator):
    """Implements the ``floor`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Floor
    (upstream ArithmeticOperators.java lines 184-200).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_floor(context.get_stack())


class IDiv(Operator):
    """Implements the ``idiv`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.IDiv
    (upstream ArithmeticOperators.java lines 203-213).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_idiv(context.get_stack())


# Backwards-compatible alias (early port used the snake-friendly name `Idiv`).
Idiv = IDiv


class Ln(Operator):
    """Implements the ``ln`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Ln
    (upstream ArithmeticOperators.java lines 216-225).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_ln(context.get_stack())


class Log(Operator):
    """Implements the ``log`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Log
    (upstream ArithmeticOperators.java lines 228-237).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_log(context.get_stack())


class Mod(Operator):
    """Implements the ``mod`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Mod
    (upstream ArithmeticOperators.java lines 240-250).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_mod(context.get_stack())


class Mul(Operator):
    """Implements the ``mul`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Mul
    (upstream ArithmeticOperators.java lines 253-279).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_mul(context.get_stack())


class Neg(Operator):
    """Implements the ``neg`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Neg
    (upstream ArithmeticOperators.java lines 282-306).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_neg(context.get_stack())


class Round(Operator):
    """Implements the ``round`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Round
    (upstream ArithmeticOperators.java lines 309-325).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_round(context.get_stack())


class Sin(Operator):
    """Implements the ``sin`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Sin
    (upstream ArithmeticOperators.java lines 328-338).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_sin(context.get_stack())


class Sqrt(Operator):
    """Implements the ``sqrt`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Sqrt
    (upstream ArithmeticOperators.java lines 341-354). Negative input
    surfaces as ``OSError`` rather than ``IllegalArgumentException`` —
    upstream behaviour rejects the negative input, the wrapper exception
    type matches the rest of the Type 4 stack machine which uses
    ``OSError`` (CLAUDE.md mapping table).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_sqrt(context.get_stack())


class Sub(Operator):
    """Implements the ``sub`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Sub
    (upstream ArithmeticOperators.java lines 357-384).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_sub(context.get_stack())


class Truncate(Operator):
    """Implements the ``truncate`` operator.

    Mirrors org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators.Truncate
    (upstream ArithmeticOperators.java lines 387-402).
    """

    def execute(self, context: ExecutionContext) -> None:
        _op_truncate(context.get_stack())


__all__ = [
    "Abs",
    "Add",
    "Atan",
    "Ceiling",
    "Cos",
    "Cvi",
    "Cvr",
    "Div",
    "ExecutionContext",
    "Exp",
    "Floor",
    "Idiv",
    "Ln",
    "Log",
    "Mod",
    "Mul",
    "Neg",
    "Operator",
    "Round",
    "Sin",
    "Sqrt",
    "Sub",
    "Truncate",
]
