"""Tests for arithmetic operator class shapes.

Mirrors upstream behaviour from
``org.apache.pdfbox.pdmodel.common.function.type4.ArithmeticOperators``.
Each test pre-loads an :class:`ExecutionContext` stack with operands,
runs the operator's ``execute`` method, and checks the resulting stack.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.pdmodel.common.function.type4 import ExecutionContext, Operator, Operators
from pypdfbox.pdmodel.common.function.type4.arithmetic_operators import (
    Abs,
    Add,
    Atan,
    Ceiling,
    Cos,
    Cvi,
    Cvr,
    Div,
    Exp,
    Floor,
    Idiv,
    Ln,
    Log,
    Mod,
    Mul,
    Neg,
    Round,
    Sin,
    Sqrt,
    Sub,
    Truncate,
)


def _ctx(*values: float) -> ExecutionContext:
    """Return a fresh ExecutionContext with ``values`` pre-pushed (left-to-right)."""
    ctx = ExecutionContext(Operators())
    ctx.get_stack().extend(values)
    return ctx


def _exec(op: Operator, *values: float) -> list[object]:
    ctx = _ctx(*values)
    op.execute(ctx)
    return ctx.get_stack()


# ---------- subclass shape ----------


def test_all_classes_subclass_operator():
    classes = [
        Abs, Add, Atan, Ceiling, Cos, Cvi, Cvr, Div, Exp, Floor, Idiv,
        Ln, Log, Mod, Mul, Neg, Round, Sin, Sqrt, Sub, Truncate,
    ]
    assert len(classes) == 21
    for cls in classes:
        assert issubclass(cls, Operator)
        # All concrete — instantiation must not raise.
        instance = cls()
        assert hasattr(instance, "execute")


# ---------- per-class behaviour ----------


def test_abs():
    assert _exec(Abs(), -3.0) == [3.0]
    assert _exec(Abs(), 5.5) == [5.5]


def test_add():
    assert _exec(Add(), 3.0, 4.0) == [7.0]
    assert _exec(Add(), -1.5, 2.5) == [1.0]


def test_atan():
    # atan2(0, 1) = 0 degrees; PostScript returns [0, 360).
    assert _exec(Atan(), 0.0, 1.0) == [0.0]
    # atan2(1, 0) = 90 degrees.
    [result] = _exec(Atan(), 1.0, 0.0)
    assert math.isclose(result, 90.0, abs_tol=1e-6)
    # atan2(-1, 0) = 270 degrees (wraps around).
    [result] = _exec(Atan(), -1.0, 0.0)
    assert math.isclose(result, 270.0, abs_tol=1e-6)


def test_ceiling():
    assert _exec(Ceiling(), 1.4) == [2.0]
    assert _exec(Ceiling(), -1.6) == [-1.0]
    assert _exec(Ceiling(), 3.0) == [3.0]


def test_cos():
    [r] = _exec(Cos(), 0.0)
    assert math.isclose(r, 1.0, abs_tol=1e-9)
    [r] = _exec(Cos(), 90.0)
    assert math.isclose(r, 0.0, abs_tol=1e-9)


def test_cvi():
    # truncates toward zero
    assert _exec(Cvi(), 3.7) == [3.0]
    assert _exec(Cvi(), -3.7) == [-3.0]


def test_cvr():
    # converts to real (already float)
    assert _exec(Cvr(), 5.0) == [5.0]


def test_div():
    assert _exec(Div(), 10.0, 4.0) == [2.5]


def test_div_by_zero_yields_infinity():
    # Upstream ArithmeticOperators$Div is plain IEEE float division: a zero
    # divisor yields +/-Infinity (NaN for 0/0), absorbed by the later /Range
    # clip. pypdfbox mirrors this rather than raising (wave 1500 parity fix).
    assert _exec(Div(), 1.0, 0.0) == [math.inf]
    assert _exec(Div(), -1.0, 0.0) == [-math.inf]
    [r] = _exec(Div(), 0.0, 0.0)
    assert math.isnan(r)


def test_exp():
    [r] = _exec(Exp(), 2.0, 10.0)
    assert math.isclose(r, 1024.0, abs_tol=1e-6)


def test_floor():
    assert _exec(Floor(), 1.6) == [1.0]
    assert _exec(Floor(), -1.4) == [-2.0]


def test_idiv():
    assert _exec(Idiv(), 7.0, 2.0) == [3.0]
    # Truncation toward zero (PostScript semantics).
    assert _exec(Idiv(), -7.0, 2.0) == [-3.0]


def test_idiv_by_zero_raises():
    with pytest.raises(OSError):
        _exec(Idiv(), 1.0, 0.0)


def test_ln():
    [r] = _exec(Ln(), math.e)
    assert math.isclose(r, 1.0, abs_tol=1e-9)


def test_ln_non_positive_yields_special():
    # Upstream Math.log(0) == -Infinity, Math.log(negative) == NaN — no domain
    # guard. pypdfbox mirrors this (wave 1500 parity fix).
    assert _exec(Ln(), 0.0) == [-math.inf]
    [r] = _exec(Ln(), -1.0)
    assert math.isnan(r)


def test_log():
    [r] = _exec(Log(), 100.0)
    assert math.isclose(r, 2.0, abs_tol=1e-9)


def test_log_non_positive_yields_special():
    # Upstream Math.log10(0) == -Infinity, Math.log10(negative) == NaN.
    assert _exec(Log(), 0.0) == [-math.inf]
    [r] = _exec(Log(), -1.0)
    assert math.isnan(r)


def test_mod():
    assert _exec(Mod(), 7.0, 3.0) == [1.0]
    # Sign follows dividend (PostScript semantics).
    assert _exec(Mod(), -7.0, 3.0) == [-1.0]


def test_mod_by_zero_raises():
    with pytest.raises(OSError):
        _exec(Mod(), 1.0, 0.0)


def test_mul():
    assert _exec(Mul(), 3.0, 4.0) == [12.0]
    assert _exec(Mul(), -2.5, 4.0) == [-10.0]


def test_neg():
    assert _exec(Neg(), 5.0) == [-5.0]
    assert _exec(Neg(), -2.5) == [2.5]


def test_round():
    # Ties go toward +infinity (PDF Type 4 semantics).
    assert _exec(Round(), 0.5) == [1.0]
    assert _exec(Round(), 1.4) == [1.0]
    assert _exec(Round(), 1.6) == [2.0]
    # Negative ties: -0.5 + 0.5 = 0 -> floor 0
    assert _exec(Round(), -0.5) == [0.0]


def test_sin():
    [r] = _exec(Sin(), 0.0)
    assert math.isclose(r, 0.0, abs_tol=1e-9)
    [r] = _exec(Sin(), 90.0)
    assert math.isclose(r, 1.0, abs_tol=1e-9)


def test_sqrt():
    assert _exec(Sqrt(), 16.0) == [4.0]
    assert _exec(Sqrt(), 0.0) == [0.0]


def test_sqrt_negative_raises():
    with pytest.raises(OSError):
        _exec(Sqrt(), -1.0)


def test_sub():
    assert _exec(Sub(), 10.0, 3.0) == [7.0]
    assert _exec(Sub(), -1.0, -2.0) == [1.0]


def test_truncate():
    assert _exec(Truncate(), 3.7) == [3.0]
    assert _exec(Truncate(), -3.7) == [-3.0]
    assert _exec(Truncate(), 5.0) == [5.0]


# ---------- chained execution mimicking PostScript composition ----------


def test_chain_add_then_mul():
    # ``2 3 add 4 mul`` => (2+3)*4 = 20
    ctx = ExecutionContext(Operators())
    ctx.get_stack().extend([2.0, 3.0])
    Add().execute(ctx)
    ctx.get_stack().append(4.0)
    Mul().execute(ctx)
    assert ctx.get_stack() == [20.0]


def test_chain_neg_abs():
    ctx = ExecutionContext(Operators())
    ctx.get_stack().append(-9.0)
    Neg().execute(ctx)
    Abs().execute(ctx)
    assert ctx.get_stack() == [9.0]
