"""Wave 1572 fuzz tests for ``PDFunctionType4`` — the PostScript calculator
stack machine (``pd_function_type4`` + the ``type4`` operator classes).

Every case is a Type 4 PostScript program driven through the public ``eval``
surface. The corpus hammers each operator family with exact numeric
expectations cross-checked against the PostScript Language Reference (3rd ed.,
§8) / PDF 32000-1 §7.10.5 and verified against Apache PDFBox 3.0.7 behaviour:

* arithmetic: add sub mul div idiv mod neg abs sqrt sin cos atan exp ln log
  cvi cvr (including int-vs-real tag preservation and 32-bit overflow)
* comparison / boolean: eq ne gt ge lt le and or not xor bitshift
* stack: dup pop exch copy index roll (with the wave-1572 roll fix below)
* conditionals: if / ifelse with procedure blocks
* rounding/truncation: round truncate ceiling floor (ties, negatives)
* /Domain input clamp + /Range output clamp (incl. div-by-zero -> clamped inf)
* edge cases: div by zero, sqrt/ln/log of negatives, atan quadrant (0..360),
  roll with negative j / |j| > n, index out of range, stack underflow

The roll-direction cases pin the wave-1572 convergence fix: upstream
``StackOperators$Roll`` does not pre-reject ``|j| > n``; it only faults on a
genuine ``stack.pop()`` underflow. The previous pypdfbox shortcut raised on
every ``|j| > n`` regardless of real stack depth.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType4


def _make(
    body: str,
    *,
    domain: list[float] | None = None,
    rng: list[float] | None = None,
) -> PDFunctionType4:
    stream = COSStream()
    stream.set_int("FunctionType", 4)
    if domain is not None:
        domain_array = COSArray()
        domain_array.set_float_array(domain)
        stream.set_item("Domain", domain_array)
    if rng is not None:
        range_array = COSArray()
        range_array.set_float_array(rng)
        stream.set_item("Range", range_array)
    stream.set_data(body.encode("ascii"))
    return PDFunctionType4(stream)


def _run(body: str, inputs: list[float] | None = None) -> list[float]:
    """Evaluate ``body`` with a generous /Domain over the supplied inputs and
    no /Range (so the bare bottom-up stack is returned, booleans coerced)."""
    if inputs is None:
        inputs = []
    domain = [-1e9, 1e9] * len(inputs) if inputs else []
    return _make(body, domain=domain).eval(inputs)


# --------------------------------------------------------------------------
# Arithmetic — exact results & int/real tagging
# --------------------------------------------------------------------------


def test_add_sub_mul_basic() -> None:
    assert _run("{ 3 4 add }") == pytest.approx([7.0])
    assert _run("{ 10 3 sub }") == pytest.approx([7.0])
    assert _run("{ 6 7 mul }") == pytest.approx([42.0])
    assert _run("{ 1.5 2.5 add }") == pytest.approx([4.0])


def test_div_always_real() -> None:
    assert _run("{ 6 2 div }") == pytest.approx([3.0])
    assert _run("{ 7 2 div }") == pytest.approx([3.5])


def test_div_by_zero_yields_infinity_not_error() -> None:
    # Upstream Div is IEEE float division: 1/0 -> +inf, -1/0 -> -inf, 0/0 -> NaN.
    assert _run("{ 1 0 div }") == [math.inf]
    assert _run("{ -1 0 div }") == [-math.inf]
    assert math.isnan(_run("{ 0 0 div }")[0])


def test_idiv_truncates_toward_zero() -> None:
    assert _run("{ 7 2 idiv }") == pytest.approx([3.0])
    assert _run("{ -7 2 idiv }") == pytest.approx([-3.0])
    assert _run("{ 7 -2 idiv }") == pytest.approx([-3.0])
    assert _run("{ -7 -2 idiv }") == pytest.approx([3.0])


def test_idiv_by_zero_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 1 0 idiv }")


def test_idiv_rejects_real_operand() -> None:
    # 7.5 is a Float; idiv casts (Integer) and raises (ClassCastException parity).
    with pytest.raises(OSError):
        _run("{ 7.5 2 idiv }")


def test_mod_sign_follows_dividend() -> None:
    assert _run("{ 7 3 mod }") == pytest.approx([1.0])
    assert _run("{ -7 3 mod }") == pytest.approx([-1.0])
    assert _run("{ 7 -3 mod }") == pytest.approx([1.0])
    assert _run("{ -7 -3 mod }") == pytest.approx([-1.0])


def test_neg_and_abs() -> None:
    assert _run("{ 5 neg }") == pytest.approx([-5.0])
    assert _run("{ -5 abs }") == pytest.approx([5.0])
    assert _run("{ -3.5 abs }") == pytest.approx([3.5])


def test_sqrt() -> None:
    assert _run("{ 9 sqrt }") == pytest.approx([3.0])
    assert _run("{ 0 sqrt }") == pytest.approx([0.0])


def test_sqrt_negative_raises() -> None:
    with pytest.raises(OSError):
        _run("{ -1 sqrt }")


def test_sin_cos_degrees() -> None:
    assert _run("{ 90 sin }") == pytest.approx([1.0])
    assert _run("{ 0 sin }") == pytest.approx([0.0])
    assert _run("{ 0 cos }") == pytest.approx([1.0])
    assert _run("{ 180 cos }") == pytest.approx([-1.0])


def test_atan_returns_degrees_in_0_360() -> None:
    # atan(num den) -> degrees in [0,360).
    assert _run("{ 0 1 atan }") == pytest.approx([0.0])
    assert _run("{ 1 0 atan }") == pytest.approx([90.0])
    assert _run("{ 1 1 atan }") == pytest.approx([45.0])
    # num=1 den=-1 -> 135 degrees (Q2). num=-1 den=-1 -> 225 (Q3 wrapped).
    assert _run("{ 1 -1 atan }") == pytest.approx([135.0])
    assert _run("{ -1 -1 atan }") == pytest.approx([225.0])
    assert _run("{ -1 0 atan }") == pytest.approx([270.0])


def test_exp_power() -> None:
    assert _run("{ 2 10 exp }") == pytest.approx([1024.0])
    assert _run("{ 9 0.5 exp }") == pytest.approx([3.0])


def test_exp_negative_base_fractional_is_nan() -> None:
    assert math.isnan(_run("{ -2 0.5 exp }")[0])


def test_ln_and_log() -> None:
    assert _run("{ 1 ln }") == pytest.approx([0.0])
    assert _run("{ 2.718281828 ln }") == pytest.approx([1.0], abs=1e-6)
    assert _run("{ 100 log }") == pytest.approx([2.0])
    assert _run("{ 1 log }") == pytest.approx([0.0])


def test_ln_log_zero_is_neg_infinity() -> None:
    assert _run("{ 0 ln }") == [-math.inf]
    assert _run("{ 0 log }") == [-math.inf]


def test_ln_log_negative_is_nan() -> None:
    assert math.isnan(_run("{ -5 ln }")[0])
    assert math.isnan(_run("{ -5 log }")[0])


def test_cvi_truncates_toward_zero_and_retags() -> None:
    assert _run("{ 7.9 cvi }") == pytest.approx([7.0])
    assert _run("{ -7.9 cvi }") == pytest.approx([-7.0])
    # Re-tag a Float as Integer so a following idiv accepts it.
    assert _run("{ 7.9 cvi 2 idiv }") == pytest.approx([3.0])


def test_cvr_retags_int_as_real() -> None:
    assert _run("{ 5 cvr }") == pytest.approx([5.0])
    # A Float cannot drive idiv even after cvr (it stays Real).
    with pytest.raises(OSError):
        _run("{ 5 cvr 2 idiv }")


# --------------------------------------------------------------------------
# Rounding / truncation
# --------------------------------------------------------------------------


def test_round_ties_toward_positive_infinity() -> None:
    # Java Math.round == floor(x + 0.5): 2.5 -> 3, -2.5 -> -2.
    assert _run("{ 2.5 round }") == pytest.approx([3.0])
    assert _run("{ -2.5 round }") == pytest.approx([-2.0])
    assert _run("{ 2.4 round }") == pytest.approx([2.0])
    assert _run("{ -2.6 round }") == pytest.approx([-3.0])


def test_truncate_floor_ceiling_negatives() -> None:
    assert _run("{ -2.7 truncate }") == pytest.approx([-2.0])
    assert _run("{ 2.7 truncate }") == pytest.approx([2.0])
    assert _run("{ -2.3 floor }") == pytest.approx([-3.0])
    assert _run("{ -2.3 ceiling }") == pytest.approx([-2.0])
    assert _run("{ 2.3 ceiling }") == pytest.approx([3.0])


def test_integer_rounding_ops_are_identity() -> None:
    assert _run("{ 5 round }") == pytest.approx([5.0])
    assert _run("{ 5 truncate }") == pytest.approx([5.0])
    assert _run("{ 5 floor }") == pytest.approx([5.0])
    assert _run("{ 5 ceiling }") == pytest.approx([5.0])


# --------------------------------------------------------------------------
# Comparison & boolean
# --------------------------------------------------------------------------


def test_relational_operators() -> None:
    assert _run("{ 3 4 lt { 1 } { 0 } ifelse }") == pytest.approx([1.0])
    assert _run("{ 4 4 le { 1 } { 0 } ifelse }") == pytest.approx([1.0])
    assert _run("{ 5 4 gt { 1 } { 0 } ifelse }") == pytest.approx([1.0])
    assert _run("{ 4 5 ge { 1 } { 0 } ifelse }") == pytest.approx([0.0])


def test_eq_ne_int_vs_float() -> None:
    assert _run("{ 5 5.0 eq { 1 } { 0 } ifelse }") == pytest.approx([1.0])
    assert _run("{ 5 6 ne { 1 } { 0 } ifelse }") == pytest.approx([1.0])


def test_eq_boolean_vs_int_never_equal() -> None:
    # Java Boolean.equals(Integer) is always false (unlike Python True == 1).
    assert _run("{ true 1 eq { 1 } { 0 } ifelse }") == pytest.approx([0.0])


def test_and_or_xor_on_ints() -> None:
    assert _run("{ 12 10 and }") == pytest.approx([8.0])
    assert _run("{ 12 10 or }") == pytest.approx([14.0])
    assert _run("{ 12 10 xor }") == pytest.approx([6.0])


def test_and_or_xor_on_bools() -> None:
    assert _run("{ true false and { 1 } { 0 } ifelse }") == pytest.approx([0.0])
    assert _run("{ true false or { 1 } { 0 } ifelse }") == pytest.approx([1.0])
    assert _run("{ true false xor { 1 } { 0 } ifelse }") == pytest.approx([1.0])


def test_and_mixed_int_bool_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 5 true and }")


def test_not_int_is_arithmetic_negation() -> None:
    # Upstream Not on an Integer is -int (not bitwise complement).
    assert _run("{ 5 not }") == pytest.approx([-5.0])
    assert _run("{ true not { 1 } { 0 } ifelse }") == pytest.approx([0.0])


def test_not_real_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 1.5 not }")


def test_bitshift_left_right_arithmetic() -> None:
    assert _run("{ 1 4 bitshift }") == pytest.approx([16.0])
    assert _run("{ 256 -2 bitshift }") == pytest.approx([64.0])
    # Arithmetic (sign-preserving) right shift of a negative.
    assert _run("{ -8 -1 bitshift }") == pytest.approx([-4.0])


def test_bitshift_count_masked_to_5_bits() -> None:
    # Java uses (shift & 0x1f): 1 << 40 == 1 << 8 == 256.
    assert _run("{ 1 40 bitshift }") == pytest.approx([256.0])


def test_bitshift_real_operand_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 1.0 2 bitshift }")


# --------------------------------------------------------------------------
# 32-bit integer wrap on arithmetic tag overflow
# --------------------------------------------------------------------------


def test_int_overflow_promotes_to_float() -> None:
    # 100000 * 100000 = 1e10 overflows int32 -> Float (not wrapped).
    assert _run("{ 100000 100000 mul }") == pytest.approx([1e10])
    assert _run("{ 2147483647 1 add }") == pytest.approx([2147483648.0])


def test_intmin_neg_abs_corner() -> None:
    # Math.abs(Integer.MIN_VALUE) stays negative; neg promotes to float.
    assert _run("{ -2147483648 neg }") == pytest.approx([2147483648.0])
    assert _run("{ -2147483648 abs }") == pytest.approx([-2147483648.0])


# --------------------------------------------------------------------------
# Stack operators
# --------------------------------------------------------------------------


def test_dup_pop_exch() -> None:
    assert _run("{ 5 dup add }") == pytest.approx([10.0])
    assert _run("{ 1 2 pop }") == pytest.approx([1.0])
    assert _run("{ 1 2 exch sub }") == pytest.approx([1.0])  # 2 - 1


def test_copy() -> None:
    # copy 2 of [3 4] -> 3 4 3 4
    assert _run("{ 3 4 2 copy }") == pytest.approx([3.0, 4.0, 3.0, 4.0])
    # copy 0 is a no-op.
    assert _run("{ 7 0 copy }") == pytest.approx([7.0])


def test_copy_overrange_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 1 5 copy }")


def test_index() -> None:
    # 0 index duplicates top.
    assert _run("{ 10 20 30 0 index }") == pytest.approx([10.0, 20.0, 30.0, 30.0])
    # 2 index reaches the element 2 below the new top.
    assert _run("{ 10 20 30 2 index }") == pytest.approx([10.0, 20.0, 30.0, 10.0])


def test_index_negative_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 10 20 -1 index }")


def test_index_overrange_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 10 20 9 index }")


def test_roll_positive() -> None:
    # 3 1 roll of (1 2 3) -> (3 1 2): top wraps to bottom.
    assert _run("{ 1 2 3 3 1 roll }") == pytest.approx([3.0, 1.0, 2.0])


def test_roll_negative() -> None:
    # 3 -1 roll of (1 2 3) -> (2 3 1): bottom wraps to top.
    assert _run("{ 1 2 3 3 -1 roll }") == pytest.approx([2.0, 3.0, 1.0])


def test_roll_zero_is_noop() -> None:
    assert _run("{ 1 2 3 3 0 roll }") == pytest.approx([1.0, 2.0, 3.0])


def test_roll_n_negative_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 1 2 3 -1 1 roll }")


def test_roll_full_rotation_is_identity() -> None:
    # j == n rotates the whole window back to itself.
    assert _run("{ 10 20 30 3 3 roll }") == pytest.approx([10.0, 20.0, 30.0])


def test_roll_j_greater_than_n_with_deep_stack() -> None:
    # WAVE 1572 FIX: upstream does NOT reject |j| > n. With a depth-6 stack and
    # n=3 j=5, it pops 5 entries and re-pushes them in order -> stack unchanged.
    # (Previously pypdfbox raised on every |j| > n.)
    assert _run("{ 10 20 30 40 50 60 3 5 roll }") == pytest.approx(
        [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    )
    assert _run("{ 10 20 30 40 50 60 3 -5 roll }") == pytest.approx(
        [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    )


def test_roll_n_zero_with_nonzero_j_pops_underlying() -> None:
    # n=0 j=5 over a depth-6 stack: pops 5, pushes back -> unchanged.
    assert _run("{ 10 20 30 40 50 60 0 5 roll }") == pytest.approx(
        [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    )


def test_roll_underflow_raises_when_stack_too_shallow() -> None:
    # n=9 over a 2-deep stack underflows the pop loop.
    with pytest.raises(OSError):
        _run("{ 1 2 9 1 roll }")
    # j=7 over a 3-deep window underflows (pops 7 from 3).
    with pytest.raises(OSError):
        _run("{ 1 2 3 3 7 roll }")


def test_roll_real_count_truncated() -> None:
    # 1.9 truncates to 1 (intValue), so behaves like 3 1 roll.
    assert _run("{ 1 2 3 3 1.9 roll }") == pytest.approx([3.0, 1.0, 2.0])


# --------------------------------------------------------------------------
# Stack underflow / type errors
# --------------------------------------------------------------------------


def test_underflow_raises() -> None:
    with pytest.raises(OSError):
        _run("{ add }")
    with pytest.raises(OSError):
        _run("{ pop }")
    with pytest.raises(OSError):
        _run("{ exch }")


def test_add_boolean_raises() -> None:
    with pytest.raises(OSError):
        _run("{ true 1 add }")


# --------------------------------------------------------------------------
# Conditionals
# --------------------------------------------------------------------------


def test_if_true_false() -> None:
    assert _run("{ true { 11 } if }") == pytest.approx([11.0])
    assert _run("{ false { 11 } if 22 }") == pytest.approx([22.0])


def test_ifelse() -> None:
    assert _run("{ true { 1 } { 2 } ifelse }") == pytest.approx([1.0])
    assert _run("{ false { 1 } { 2 } ifelse }") == pytest.approx([2.0])


def test_if_non_boolean_condition_raises() -> None:
    with pytest.raises(OSError):
        _run("{ 1 { 11 } if }")


def test_nested_if() -> None:
    # Inner block needs its own boolean before the nested ``if``.
    assert _run("{ true { 2 true { 3 } if } if }") == pytest.approx([2.0, 3.0])


def test_unknown_operator_raises() -> None:
    with pytest.raises(OSError):
        _run("{ frobnicate }")


# --------------------------------------------------------------------------
# /Domain input clamp and /Range output clamp
# --------------------------------------------------------------------------


def test_domain_clamps_input() -> None:
    fn = _make("{ }", domain=[0.0, 1.0], rng=[-1000.0, 1000.0])
    # Input 5 is clamped to 1 by /Domain before the program runs.
    assert fn.eval([5.0]) == pytest.approx([1.0])
    assert fn.eval([-5.0]) == pytest.approx([0.0])


def test_range_clamps_output() -> None:
    fn = _make("{ pop 5000 }", domain=[0.0, 1.0], rng=[-10.0, 10.0])
    assert fn.eval([0.5]) == pytest.approx([10.0])
    fn_low = _make("{ pop -5000 }", domain=[0.0, 1.0], rng=[-10.0, 10.0])
    assert fn_low.eval([0.5]) == pytest.approx([-10.0])


def test_range_clamps_infinity_from_div_zero() -> None:
    fn = _make("{ pop 1 0 div }", domain=[0.0, 1.0], rng=[-10.0, 10.0])
    assert fn.eval([0.5]) == pytest.approx([10.0])
    fn_neg = _make("{ pop -1 0 div }", domain=[0.0, 1.0], rng=[-10.0, 10.0])
    assert fn_neg.eval([0.5]) == pytest.approx([-10.0])


def test_range_undersupply_raises() -> None:
    # /Range declares one output but the program leaves nothing.
    fn = _make("{ pop }", domain=[0.0, 1.0], rng=[-10.0, 10.0])
    with pytest.raises(OSError):
        fn.eval([0.5])


def test_range_boolean_output_raises() -> None:
    # A Boolean left in a declared /Range slot is a runtime fault (Number cast).
    fn = _make("{ pop 5 5 eq }", domain=[0.0, 1.0], rng=[-10.0, 10.0])
    with pytest.raises(OSError):
        fn.eval([0.5])


def test_multi_output_program() -> None:
    fn = _make(
        "{ dup 100 mul exch 200 mul }",
        domain=[0.0, 1.0],
        rng=[-1000.0, 1000.0, -1000.0, 1000.0],
    )
    # input 0.5: dup;100 mul;exch;200 mul leaves the stack [50, 100], returned
    # bottom-up after the top-N output fill -> [50, 100].
    assert fn.eval([0.5]) == pytest.approx([50.0, 100.0])
