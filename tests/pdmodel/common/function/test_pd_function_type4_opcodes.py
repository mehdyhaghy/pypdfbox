"""Per-opcode coverage tests for ``PDFunctionType4``.

Exercises each PostScript-calculator operator the executor recognises
through the public ``eval`` surface, plus a few control-flow / nesting
shapes for ``if`` / ``ifelse``. These complement the cache-behaviour
tests in ``test_pd_function_type4.py`` and the upstream-ported tests in
``upstream/test_pd_function_type4_operators.py``.

Inputs go through ``clip_input``; we use a generous ``/Domain`` to keep
the inputs untouched. Outputs go through ``clip_output`` only when
``/Range`` is supplied — we omit ``/Range`` so the raw stack is returned.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType4


def _make(body: str, domain: list[float] | None = None) -> PDFunctionType4:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    if domain is None:
        domain = [-1e9, 1e9]
    arr = COSArray()
    arr.set_float_array(domain)
    raw.set_item("Domain", arr)
    raw.set_data(body.encode("utf-8"))
    return PDFunctionType4(raw)


def _run(body: str, inputs: list[float] | None = None) -> list[float]:
    """Evaluate ``body`` with no input dimensions; return the bare stack."""
    if inputs is None:
        inputs = []
    # When inputs are empty, set Domain to an empty array so clip_input
    # passes nothing through.
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    arr = COSArray()
    arr.set_float_array([] if not inputs else [-1e9, 1e9] * len(inputs))
    raw.set_item("Domain", arr)
    raw.set_data(body.encode("utf-8"))
    return PDFunctionType4(raw).eval(inputs)


# --------------------------------------------------------------------------
# Arithmetic
# --------------------------------------------------------------------------


def test_add() -> None:
    assert _run("{ 5 6 add }") == pytest.approx([11.0])
    assert _run("{ 5 0.25 add }") == pytest.approx([5.25])


def test_sub() -> None:
    assert _run("{ 5 2 sub }") == pytest.approx([3.0])
    assert _run("{ -7.5 1 sub }") == pytest.approx([-8.5])


def test_mul() -> None:
    assert _run("{ 1.5 2 mul }") == pytest.approx([3.0])
    assert _run("{ 1.5 2.1 mul }") == pytest.approx([3.15])


def test_div() -> None:
    assert _run("{ 3 2 div }") == pytest.approx([1.5])
    assert _run("{ 4 2 div }") == pytest.approx([2.0])


def test_div_by_zero_yields_infinity() -> None:
    # IEEE float division (no /Range here to clip): 1/0 == +Infinity. pypdfbox
    # mirrors upstream rather than raising (wave 1500 parity fix).
    [r] = _run("{ 1 0 div }")
    assert r == math.inf


def test_idiv() -> None:
    # Truncation toward zero, not floor.
    assert _run("{ 3 2 idiv }") == pytest.approx([1.0])
    assert _run("{ -5 2 idiv }") == pytest.approx([-2.0])
    assert _run("{ 5 -2 idiv }") == pytest.approx([-2.0])


def test_idiv_rejects_non_integer() -> None:
    with pytest.raises(OSError):
        _run("{ 4.4 2 idiv }")


def test_mod() -> None:
    # Sign of result follows dividend (matches Java %).
    assert _run("{ 5 3 mod }") == pytest.approx([2.0])
    assert _run("{ -5 3 mod }") == pytest.approx([-2.0])


def test_mod_rejects_non_integer() -> None:
    with pytest.raises(OSError):
        _run("{ 4.4 2 mod }")


def test_neg() -> None:
    assert _run("{ 4.5 neg }") == pytest.approx([-4.5])
    assert _run("{ -3 neg }") == pytest.approx([3.0])


def test_abs() -> None:
    assert _run("{ -3 abs }") == pytest.approx([3.0])
    assert _run("{ 2.1 abs }") == pytest.approx([2.1])
    assert _run("{ -7.5 abs }") == pytest.approx([7.5])


def test_ceiling() -> None:
    assert _run("{ 3.2 ceiling }") == pytest.approx([4.0])
    assert _run("{ -4.8 ceiling }") == pytest.approx([-4.0])
    assert _run("{ 99 ceiling }") == pytest.approx([99.0])


def test_floor() -> None:
    assert _run("{ 3.2 floor }") == pytest.approx([3.0])
    assert _run("{ -4.8 floor }") == pytest.approx([-5.0])
    assert _run("{ 99 floor }") == pytest.approx([99.0])


def test_round() -> None:
    # PostScript: ties go toward +infinity.
    assert _run("{ 3.2 round }") == pytest.approx([3.0])
    assert _run("{ 6.5 round }") == pytest.approx([7.0])
    assert _run("{ -4.8 round }") == pytest.approx([-5.0])
    # -6.5 + 0.5 = -6.0; floor(-6.0) = -6.0. PostScript rounds half toward +inf.
    assert _run("{ -6.5 round }") == pytest.approx([-6.0])
    assert _run("{ 99 round }") == pytest.approx([99.0])


def test_truncate() -> None:
    assert _run("{ 3.2 truncate }") == pytest.approx([3.0])
    assert _run("{ -4.8 truncate }") == pytest.approx([-4.0])
    assert _run("{ 99 truncate }") == pytest.approx([99.0])


def test_sqrt() -> None:
    assert _run("{ 0 sqrt }") == pytest.approx([0.0])
    assert _run("{ 4 sqrt }") == pytest.approx([2.0])
    assert _run("{ 4.4 sqrt }") == pytest.approx([2.0976176963], rel=1e-6)


def test_sqrt_negative_raises() -> None:
    with pytest.raises(OSError):
        _run("{ -4.1 sqrt }")


def test_sin() -> None:
    assert _run("{ 0 sin }") == pytest.approx([0.0])
    assert _run("{ 90 sin }") == pytest.approx([1.0])
    assert _run("{ -90.0 sin }") == pytest.approx([-1.0])


def test_cos() -> None:
    assert _run("{ 0 cos }") == pytest.approx([1.0])
    assert _run("{ 90 cos }") == pytest.approx([0.0], abs=1e-10)


def test_atan() -> None:
    # PostScript atan returns degrees in [0, 360).
    assert _run("{ 0 1 atan }") == pytest.approx([0.0])
    assert _run("{ 1 0 atan }") == pytest.approx([90.0])
    assert _run("{ -100 0 atan }") == pytest.approx([270.0])
    assert _run("{ 4 4 atan }") == pytest.approx([45.0])


def test_exp() -> None:
    assert _run("{ 9 0.5 exp }") == pytest.approx([3.0])
    assert _run("{ -9 -1 exp }") == pytest.approx([-1.0 / 9.0], rel=1e-6)


def test_ln() -> None:
    assert _run("{ 10 ln }") == pytest.approx([2.30258509], rel=1e-6)
    assert _run("{ 100 ln }") == pytest.approx([4.60517018], rel=1e-6)


def test_ln_non_positive_yields_special() -> None:
    # Upstream Math.log has no domain guard: log(0) == -Infinity (clamped to
    # /Range min downstream), log(negative) == NaN. pypdfbox mirrors this
    # (wave 1500 parity fix) rather than raising.
    [r] = _run("{ 0 ln }")
    assert r == -math.inf
    [r2] = _run("{ -5 ln }")
    assert math.isnan(r2)


def test_log() -> None:
    assert _run("{ 10 log }") == pytest.approx([1.0])
    assert _run("{ 100 log }") == pytest.approx([2.0])


def test_log_non_positive_yields_special() -> None:
    # log10(negative) == NaN, log10(0) == -Infinity (wave 1500 parity fix).
    [r] = _run("{ -1 log }")
    assert math.isnan(r)
    [r2] = _run("{ 0 log }")
    assert r2 == -math.inf


def test_cvi() -> None:
    assert _run("{ -47.8 cvi }") == pytest.approx([-47.0])
    assert _run("{ 520.9 cvi }") == pytest.approx([520.0])


def test_cvr() -> None:
    assert _run("{ -47.8 cvr }") == pytest.approx([-47.8])
    assert _run("{ 77 cvr }") == pytest.approx([77.0])


# --------------------------------------------------------------------------
# Stack
# --------------------------------------------------------------------------


def test_dup() -> None:
    assert _run("{ 1 2 dup }") == pytest.approx([1.0, 2.0, 2.0])


def test_dup_underflow_raises() -> None:
    with pytest.raises(OSError):
        _run("{ dup }")


def test_exch() -> None:
    assert _run("{ 1 2.5 exch }") == pytest.approx([2.5, 1.0])


def test_pop() -> None:
    assert _run("{ 1 pop 7 2 pop }") == pytest.approx([7.0])


def test_pop_underflow_raises() -> None:
    with pytest.raises(OSError):
        _run("{ pop }")


def test_copy() -> None:
    # `1 2 3 3 copy` -> [1,2,3,1,2,3]
    assert _run("{ 1 2 3 3 copy }") == pytest.approx([1.0, 2.0, 3.0, 1.0, 2.0, 3.0])


def test_copy_zero() -> None:
    assert _run("{ 1 2 0 copy }") == pytest.approx([1.0, 2.0])


def test_copy_out_of_range_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 1 2 5 copy }")


def test_index() -> None:
    # Top of stack is index 0.
    assert _run("{ 1 2 3 4 0 index }") == pytest.approx([1.0, 2.0, 3.0, 4.0, 4.0])
    assert _run("{ 1 2 3 4 3 index }") == pytest.approx([1.0, 2.0, 3.0, 4.0, 1.0])


def test_index_out_of_range_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 1 2 3 4 4 index }")


def test_roll_positive() -> None:
    # `1 2 3 4 5 5 2 roll` -> top 2 elements get rolled to the bottom of
    # the n-element window: [4,5,1,2,3].
    assert _run("{ 1 2 3 4 5 5 2 roll }") == pytest.approx(
        [4.0, 5.0, 1.0, 2.0, 3.0]
    )


def test_roll_negative() -> None:
    # `1 2 3 4 5 5 -2 roll` -> [3,4,5,1,2].
    assert _run("{ 1 2 3 4 5 5 -2 roll }") == pytest.approx(
        [3.0, 4.0, 5.0, 1.0, 2.0]
    )


def test_roll_zero_is_noop() -> None:
    assert _run("{ 1 2 3 3 0 roll }") == pytest.approx([1.0, 2.0, 3.0])


# --------------------------------------------------------------------------
# Boolean / relational
# --------------------------------------------------------------------------


def test_eq_numeric() -> None:
    assert _run("{ 7 7 eq }") == pytest.approx([1.0])
    assert _run("{ 7 6 eq }") == pytest.approx([0.0])


def test_eq_boolean() -> None:
    assert _run("{ true true eq }") == pytest.approx([1.0])
    assert _run("{ false true eq }") == pytest.approx([0.0])


def test_ne() -> None:
    assert _run("{ 7 7 ne }") == pytest.approx([0.0])
    assert _run("{ 7 6 ne }") == pytest.approx([1.0])


def test_lt() -> None:
    assert _run("{ 5 7 lt }") == pytest.approx([1.0])
    assert _run("{ 7 7 lt }") == pytest.approx([0.0])


def test_le() -> None:
    assert _run("{ 7 7 le }") == pytest.approx([1.0])
    assert _run("{ 7 5 le }") == pytest.approx([0.0])


def test_gt() -> None:
    assert _run("{ 7 5 gt }") == pytest.approx([1.0])
    assert _run("{ 7 7 gt }") == pytest.approx([0.0])


def test_ge() -> None:
    assert _run("{ 7 7 ge }") == pytest.approx([1.0])
    assert _run("{ 5 7 ge }") == pytest.approx([0.0])


def test_and_bool() -> None:
    assert _run("{ true true and }") == pytest.approx([1.0])
    assert _run("{ true false and }") == pytest.approx([0.0])


def test_and_int() -> None:
    assert _run("{ 99 1 and }") == pytest.approx([1.0])
    assert _run("{ 52 7 and }") == pytest.approx([4.0])


def test_or_bool() -> None:
    assert _run("{ true false or }") == pytest.approx([1.0])
    assert _run("{ false false or }") == pytest.approx([0.0])


def test_or_int() -> None:
    assert _run("{ 17 5 or }") == pytest.approx([21.0])


def test_xor_bool() -> None:
    assert _run("{ true false xor }") == pytest.approx([1.0])
    assert _run("{ true true xor }") == pytest.approx([0.0])


def test_xor_int() -> None:
    assert _run("{ 7 3 xor }") == pytest.approx([4.0])


def test_not_bool() -> None:
    assert _run("{ true not }") == pytest.approx([0.0])
    assert _run("{ false not }") == pytest.approx([1.0])


def test_not_int_is_arithmetic_negation() -> None:
    # Upstream PDFBox 3.0 treats ``not`` on int as arithmetic negation,
    # not bitwise complement. We mirror that.
    assert _run("{ 52 not }") == pytest.approx([-52.0])
    assert _run("{ -37 not }") == pytest.approx([37.0])


def test_bitshift_left() -> None:
    # 7 << 3 == 56
    assert _run("{ 7 3 bitshift }") == pytest.approx([56.0])


def test_bitshift_right() -> None:
    # 142 >> 3 == 17 (negative shift = right shift)
    assert _run("{ 142 -3 bitshift }") == pytest.approx([17.0])


def test_true_false_literals() -> None:
    assert _run("{ true }") == pytest.approx([1.0])
    assert _run("{ false }") == pytest.approx([0.0])


# --------------------------------------------------------------------------
# Conditional + nesting
# --------------------------------------------------------------------------


def test_if_true_executes_proc() -> None:
    assert _run("{ true { 2 1 add } if }") == pytest.approx([3.0])


def test_if_false_skips_proc() -> None:
    assert _run("{ false { 2 1 add } if }") == []


def test_ifelse_branches() -> None:
    assert _run("{ true { 2 1 add } { 2 1 sub } ifelse }") == pytest.approx([3.0])
    assert _run("{ false { 2 1 add } { 2 1 sub } ifelse }") == pytest.approx([1.0])


def test_if_non_boolean_condition_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 0 { 1 } if }")


def test_nested_ifelse() -> None:
    """``ifelse`` inside another branch — exercises the recursive
    sub-procedure execution path."""
    # If true, run the inner ifelse with a true condition: yields 10.
    body = (
        "{ true "
        "  { true { 10 } { 20 } ifelse } "
        "  { 30 } "
        "ifelse }"
    )
    assert _run(body) == pytest.approx([10.0])
    # If outer false, jumps to the else branch: yields 30.
    body = (
        "{ false "
        "  { true { 10 } { 20 } ifelse } "
        "  { 30 } "
        "ifelse }"
    )
    assert _run(body) == pytest.approx([30.0])


def test_nested_if_inside_ifelse() -> None:
    """An ``if`` nested inside the true branch of an ``ifelse``: the
    inner proc must consume both items it pushes when its condition
    fires and contribute nothing when it doesn't."""
    body = (
        "{ true "
        "  { 5 false { 100 add } if } "
        "  { 0 } "
        "ifelse }"
    )
    # Inner if-condition is false, so 100-add is skipped; stack ends [5].
    assert _run(body) == pytest.approx([5.0])
    body = (
        "{ true "
        "  { 5 true { 100 add } if } "
        "  { 0 } "
        "ifelse }"
    )
    # Inner if fires: 5 + 100 = 105.
    assert _run(body) == pytest.approx([105.0])


# --------------------------------------------------------------------------
# Programs combining multiple opcodes
# --------------------------------------------------------------------------


def test_squaring_program() -> None:
    fn = _make("{ dup mul }", domain=[-100.0, 100.0])
    assert fn.eval([3.0]) == pytest.approx([9.0])
    assert fn.eval([-7.0]) == pytest.approx([49.0])


def test_two_input_average() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    arr = COSArray()
    arr.set_float_array([-1e9, 1e9, -1e9, 1e9])
    raw.set_item("Domain", arr)
    raw.set_data(b"{ add 2 div }")
    fn = PDFunctionType4(raw)
    assert fn.eval([4.0, 6.0]) == pytest.approx([5.0])
