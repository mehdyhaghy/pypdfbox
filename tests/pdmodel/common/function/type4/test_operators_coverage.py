"""Coverage-boost tests for :mod:`pypdfbox.pdmodel.common.function.type4.operators`.

Targets the branches the hand-written :mod:`test_operators` suite leaves
uncovered:

* The :class:`_LegacyOperatorAdapter` fallback path — exercised by
  monkey-patching ``_resolve_class`` to return ``None`` so :meth:`_build`
  falls through to the adapter; the adapter's ``NotImplementedError``
  branch is exercised by registering a bogus name.
* The :class:`_BuiltinIf` / :class:`_BuiltinIfElse` shims — exercised by
  forcing :meth:`_build` to skip the resolved subclass and fall back to
  the built-in shim for both ``if`` and ``ifelse``. Type-check failures
  on the proc / condition slots are also exercised.
* :func:`_resolve_class` cases — ``ModuleNotFoundError`` (importable
  module path absent), attribute resolves to a non-class object, and
  attribute resolves to a class that isn't an :class:`Operator`
  subclass. All three must return ``None``.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4 import (
    ExecutionContext,
    InstructionSequence,
    Operator,
    Operators,
)
from pypdfbox.pdmodel.common.function.type4 import operators as ops_module
from pypdfbox.pdmodel.common.function.type4.operators import (
    _BuiltinIf,
    _BuiltinIfElse,
    _LegacyOperatorAdapter,
    _resolve_class,
)

# ---------- _resolve_class branches ----------------------------------------


def test_resolve_class_missing_module_returns_none() -> None:
    """Importing a module path that doesn't exist must yield ``None`` so
    the registry falls back to a legacy adapter / built-in shim."""
    assert _resolve_class("pypdfbox.does.not.exist.anywhere", "Anything") is None


def test_resolve_class_missing_attribute_returns_none() -> None:
    """A real module that lacks the requested attribute yields ``None``."""
    assert _resolve_class("pypdfbox.pdmodel.common.function.type4.operators",
                         "DefinitelyNotAClassName") is None


def test_resolve_class_attribute_is_not_a_type_returns_none() -> None:
    """``getattr`` returning a non-class object yields ``None``."""
    # ``_ARITHMETIC_NAMES`` is a tuple, not a class.
    assert _resolve_class("pypdfbox.pdmodel.common.function.type4.operators",
                         "_ARITHMETIC_NAMES") is None


def test_resolve_class_attribute_is_unrelated_class_returns_none() -> None:
    """A real class that isn't an Operator subclass yields ``None``."""
    # ``Operators`` itself is a class but not an ``Operator`` subclass.
    assert _resolve_class("pypdfbox.pdmodel.common.function.type4.operators",
                         "Operators") is None


def test_resolve_class_valid_subclass_returns_class() -> None:
    """Sanity: a real Operator subclass resolves through happy path."""
    cls = _resolve_class(
        "pypdfbox.pdmodel.common.function.type4.operators",
        "_BuiltinIf",
    )
    assert cls is _BuiltinIf


# ---------- _LegacyOperatorAdapter ------------------------------------------


def test_legacy_adapter_runs_known_operator() -> None:
    """A real operator name routed through the adapter must execute."""
    adapter = _LegacyOperatorAdapter("add")
    ctx = ExecutionContext(Operators())
    ctx.get_stack().extend([2, 3])
    adapter.execute(ctx)
    assert ctx.get_stack() == [5]


def test_legacy_adapter_unknown_name_raises_not_implemented() -> None:
    """Adapter pointed at a name the legacy executor doesn't know must
    raise ``NotImplementedError`` (line 50)."""
    adapter = _LegacyOperatorAdapter("definitely_not_an_op")
    ctx = ExecutionContext(Operators())
    with pytest.raises(NotImplementedError, match="definitely_not_an_op"):
        adapter.execute(ctx)


# ---------- _BuiltinIf -----------------------------------------------------


def _force_builtin_shims(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make :meth:`_build` fall through to the built-in if/ifelse shims
    by stubbing :func:`_resolve_class` to always return ``None``."""
    monkeypatch.setattr(ops_module, "_resolve_class", lambda *a, **k: None)


def test_builtin_if_runs_proc_when_true(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_builtin_shims(monkeypatch)
    registry = Operators()
    if_op = registry.get_operator("if")
    assert isinstance(if_op, _BuiltinIf)
    ctx = ExecutionContext(registry)
    proc = InstructionSequence()
    proc.add_integer(99)
    ctx.get_stack().extend([True, proc])
    if_op.execute(ctx)
    assert ctx.get_stack() == [99]


def test_builtin_if_skips_proc_when_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_builtin_shims(monkeypatch)
    registry = Operators()
    if_op = registry.get_operator("if")
    ctx = ExecutionContext(registry)
    proc = InstructionSequence()
    proc.add_integer(99)
    ctx.get_stack().extend([False, proc])
    if_op.execute(ctx)
    assert ctx.get_stack() == []


def test_builtin_if_rejects_non_proc_top() -> None:
    """``if`` requires an :class:`InstructionSequence` on top of the
    stack — anything else is a ``TypeError``."""
    ctx = ExecutionContext(Operators())
    ctx.get_stack().extend([True, "not a proc"])
    with pytest.raises(TypeError, match="procedure"):
        _BuiltinIf().execute(ctx)


def test_builtin_if_rejects_non_bool_condition() -> None:
    ctx = ExecutionContext(Operators())
    proc = InstructionSequence()
    ctx.get_stack().extend([1, proc])  # int not bool
    with pytest.raises(TypeError, match="boolean condition"):
        _BuiltinIf().execute(ctx)


# ---------- _BuiltinIfElse --------------------------------------------------


def test_builtin_ifelse_runs_true_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_builtin_shims(monkeypatch)
    registry = Operators()
    ifelse_op = registry.get_operator("ifelse")
    assert isinstance(ifelse_op, _BuiltinIfElse)
    ctx = ExecutionContext(registry)
    proc_true = InstructionSequence()
    proc_true.add_integer(1)
    proc_false = InstructionSequence()
    proc_false.add_integer(2)
    ctx.get_stack().extend([True, proc_true, proc_false])
    ifelse_op.execute(ctx)
    assert ctx.get_stack() == [1]


def test_builtin_ifelse_runs_false_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_builtin_shims(monkeypatch)
    registry = Operators()
    ifelse_op = registry.get_operator("ifelse")
    ctx = ExecutionContext(registry)
    proc_true = InstructionSequence()
    proc_true.add_integer(1)
    proc_false = InstructionSequence()
    proc_false.add_integer(2)
    ctx.get_stack().extend([False, proc_true, proc_false])
    ifelse_op.execute(ctx)
    assert ctx.get_stack() == [2]


def test_builtin_ifelse_rejects_non_proc_top() -> None:
    ctx = ExecutionContext(Operators())
    proc = InstructionSequence()
    ctx.get_stack().extend([True, proc, "not a proc"])
    with pytest.raises(TypeError, match="two procedures"):
        _BuiltinIfElse().execute(ctx)


def test_builtin_ifelse_rejects_non_proc_under_top() -> None:
    ctx = ExecutionContext(Operators())
    proc = InstructionSequence()
    ctx.get_stack().extend([True, "not a proc", proc])
    with pytest.raises(TypeError, match="two procedures"):
        _BuiltinIfElse().execute(ctx)


def test_builtin_ifelse_rejects_non_bool_condition() -> None:
    ctx = ExecutionContext(Operators())
    proc_t = InstructionSequence()
    proc_f = InstructionSequence()
    ctx.get_stack().extend([0, proc_t, proc_f])  # int not bool
    with pytest.raises(TypeError, match="boolean condition"):
        _BuiltinIfElse().execute(ctx)


# ---------- _build fallback paths ------------------------------------------


def test_build_falls_back_to_builtin_if_when_subclass_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the conditional_operators module can't be resolved, ``if``
    must drop to the built-in shim (line 185)."""
    _force_builtin_shims(monkeypatch)
    registry = Operators()
    assert isinstance(registry.get_operator("if"), _BuiltinIf)


def test_build_falls_back_to_builtin_ifelse_when_subclass_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Likewise for ``ifelse`` (line 187)."""
    _force_builtin_shims(monkeypatch)
    registry = Operators()
    assert isinstance(registry.get_operator("ifelse"), _BuiltinIfElse)


def test_build_falls_back_to_legacy_adapter_for_arithmetic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the arithmetic_operators module can't be resolved, ``add``
    must drop to a :class:`_LegacyOperatorAdapter` (line 189)."""
    _force_builtin_shims(monkeypatch)
    registry = Operators()
    add_op = registry.get_operator("add")
    assert isinstance(add_op, _LegacyOperatorAdapter)
    # And it still works through the legacy executor.
    ctx = ExecutionContext(registry)
    ctx.get_stack().extend([10, 20])
    add_op.execute(ctx)
    assert ctx.get_stack() == [30]


# ---------- Operator abstract base sanity ----------------------------------


def test_operator_abstract_cannot_instantiate() -> None:
    """:class:`Operator` is abstract — instantiating it directly fails."""
    with pytest.raises(TypeError):
        Operator()  # type: ignore[abstract]
