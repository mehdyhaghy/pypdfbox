"""Operator registry for Type 4 (PostScript calculator) functions.

Mirrors upstream
``org.apache.pdfbox.pdmodel.common.function.type4.Operators``. The
upstream ``Operators`` constructor instantiates one singleton per
operator class and registers it under its PostScript name; we follow
the same shape.

Cross-agent integration: the operator subclasses
(``ArithmeticOperators``, ``BitwiseOperators``, ``ConditionalOperators``,
``RelationalOperators``, ``StackOperators``) live in sibling modules
owned by parallel agents. Imports here are guarded so this module
imports cleanly even when one or more sibling modules are missing
during a wave-in-progress; any operator names whose subclass module is
absent fall back to a thin :class:`Operator` shim that delegates to the
canonical inline executor in
:mod:`pypdfbox.pdmodel.common.function.pd_function_type4`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import pd_function_type4 as _legacy
from .instruction_sequence import InstructionSequence
from .operator import Operator

if TYPE_CHECKING:
    from .execution_context import ExecutionContext


class _LegacyOperatorAdapter(Operator):
    """Wraps a function-style operator from
    :mod:`pypdfbox.pdmodel.common.function.pd_function_type4` in the
    upstream :class:`Operator` shape so the registry can hand back a
    real ``Operator`` instance even when the dedicated subclass module
    has not been ported yet.

    Not part of the upstream API surface; an internal shim only.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    def execute(self, context: ExecutionContext) -> None:
        callable_op = _legacy.get_operator(self._name)
        if callable_op is None:
            raise NotImplementedError(
                f"Unknown operator or name: {self._name}"
            )
        callable_op(context.get_stack())


class _BuiltinIf(Operator):
    """Built-in ``if`` operator — needed by the registry before the
    dedicated ``conditional_operators`` module lands so nested
    procedures (which the new parser builds as
    :class:`InstructionSequence`) are dispatched correctly. Replaced by
    ``ConditionalOperators.If`` once that module is available.
    """

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        proc = stack.pop()
        cond = stack.pop()
        if not isinstance(proc, InstructionSequence):
            raise TypeError("if expects a procedure on top of stack")
        if not isinstance(cond, bool):
            raise TypeError("if expects a boolean condition")
        if cond:
            proc.execute(context)


class _BuiltinIfElse(Operator):
    """Built-in ``ifelse`` operator — see :class:`_BuiltinIf`."""

    def execute(self, context: ExecutionContext) -> None:
        stack = context.get_stack()
        proc_false = stack.pop()
        proc_true = stack.pop()
        cond = stack.pop()
        if not (
            isinstance(proc_true, InstructionSequence)
            and isinstance(proc_false, InstructionSequence)
        ):
            raise TypeError("ifelse expects two procedures")
        if not isinstance(cond, bool):
            raise TypeError("ifelse expects a boolean condition")
        (proc_true if cond else proc_false).execute(context)


# Names of every operator the Type 4 spec recognises, grouped by
# upstream Java source file. Order within each group matches the
# upstream ``Operators`` constructor for diff parity.
_ARITHMETIC_NAMES = (
    "add", "abs", "atan", "ceiling", "cos", "cvi", "cvr", "div", "exp",
    "floor", "idiv", "ln", "log", "mod", "mul", "neg", "round", "sin",
    "sqrt", "sub", "truncate",
)
_BITWISE_NAMES = ("and", "bitshift", "false", "not", "or", "true", "xor")
_RELATIONAL_NAMES = ("eq", "ge", "gt", "le", "lt", "ne")
_CONDITIONAL_NAMES = ("if", "ifelse")
_STACK_NAMES = ("copy", "dup", "exch", "index", "pop", "roll")


def _resolve_class(module_path: str, class_name: str) -> type[Operator] | None:
    """Best-effort import of ``module_path.class_name``. Returns
    ``None`` when the module isn't on the path yet (parallel-wave
    in-flight) or the class isn't defined."""
    import importlib

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        return None
    cls = getattr(module, class_name, None)
    if cls is None or not isinstance(cls, type):
        return None
    if not issubclass(cls, Operator):
        return None
    return cls


# Mapping of upstream Java nested-class names to their PostScript
# operator names. Upstream uses e.g. ``ArithmeticOperators.IDiv`` for
# the ``"idiv"`` operator; we keep the same class names so a sibling
# module importing as ``from .arithmetic_operators import IDiv`` works
# unchanged.
_CLASS_NAMES_BY_OP: dict[str, str] = {
    "add": "Add", "abs": "Abs", "atan": "Atan", "ceiling": "Ceiling",
    "cos": "Cos", "cvi": "Cvi", "cvr": "Cvr", "div": "Div", "exp": "Exp",
    "floor": "Floor", "idiv": "IDiv", "ln": "Ln", "log": "Log",
    "mod": "Mod", "mul": "Mul", "neg": "Neg", "round": "Round",
    "sin": "Sin", "sqrt": "Sqrt", "sub": "Sub", "truncate": "Truncate",
    # ``true`` / ``false`` map to ``TrueFunc`` / ``FalseFunc``: upstream
    # names the nested classes ``True`` / ``False``, but those are
    # reserved keywords in Python, so the ported classes carry the
    # ``Func`` suffix. The PostScript operator names stay ``"true"`` /
    # ``"false"``.
    "and": "And", "bitshift": "Bitshift", "false": "FalseFunc", "not": "Not",
    "or": "Or", "true": "TrueFunc", "xor": "Xor",
    "eq": "Eq", "ge": "Ge", "gt": "Gt", "le": "Le", "lt": "Lt", "ne": "Ne",
    "if": "If", "ifelse": "IfElse",
    "copy": "Copy", "dup": "Dup", "exch": "Exch", "index": "Index",
    "pop": "Pop", "roll": "Roll",
}

_MODULE_BY_OP: dict[str, str] = (
    {n: ".arithmetic_operators" for n in _ARITHMETIC_NAMES}
    | {n: ".bitwise_operators" for n in _BITWISE_NAMES}
    | {n: ".relational_operators" for n in _RELATIONAL_NAMES}
    | {n: ".conditional_operators" for n in _CONDITIONAL_NAMES}
    | {n: ".stack_operators" for n in _STACK_NAMES}
)


class Operators:
    """Provides all the supported operators for Type 4 PostScript
    functions.

    Mirrors upstream ``Operators``. The constructor populates an
    internal name → :class:`Operator` map matching upstream's 42
    entries; :meth:`get_operator` is the lookup API.
    """

    def __init__(self) -> None:
        self._operators: dict[str, Operator] = {}
        # Order mirrors upstream constructor for parity.
        for name in (
            *_ARITHMETIC_NAMES,
            *_BITWISE_NAMES,
            *_RELATIONAL_NAMES,
            *_CONDITIONAL_NAMES,
            *_STACK_NAMES,
        ):
            self._operators[name] = self._build(name)

    @staticmethod
    def _build(name: str) -> Operator:
        module_path = "pypdfbox.pdmodel.common.function.type4" + _MODULE_BY_OP[name]
        cls = _resolve_class(module_path, _CLASS_NAMES_BY_OP[name])
        if cls is not None:
            return cls()
        # ``if`` / ``ifelse`` consume :class:`InstructionSequence` procs,
        # which the legacy executor (which expects raw lists) can't
        # dispatch. Use built-in shims that talk to the new model.
        if name == "if":
            return _BuiltinIf()
        if name == "ifelse":
            return _BuiltinIfElse()
        # Fallback: delegate to the canonical executor.
        return _LegacyOperatorAdapter(name)

    def get_operator(self, operator_name: str) -> Operator | None:
        """Return the operator for the given operator name.

        :param operator_name: the operator name
        :return: the operator (or ``None`` when no such operator exists)
        """
        return self._operators.get(operator_name)


__all__ = ["Operators"]
