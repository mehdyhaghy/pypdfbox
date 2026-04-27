"""Tests ported from upstream PDFBox 3.0
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestOperators.java``.

Upstream uses a ``Type4Tester`` fluent helper that pops values bottom-up
from the execution stack with type-aware assertions (``pop(int)`` /
``popReal(float)``). pypdfbox's ``PDFunctionType4.eval`` returns the
remaining stack as a ``list[float]`` (booleans coerced to 1.0/0.0,
upstream-stack-bottom first). We translate ``Type4Tester`` chains by
asserting against the equivalent flat ``list[float]``.

Skipped:
* Java integer-overflow checks (``Integer.MAX_VALUE`` etc.) — Python
  ints are unbounded so the cast-to-float-on-overflow upstream behaviour
  has no analogue.
* Type-distinction checks (``assertTrue(x instanceof Float)``) — pypdfbox
  collapses to ``float`` on the way out.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType4


def _eval(body: str) -> list[float]:
    """Run a Type 4 body that consumes no inputs; return the bottom-up stack."""
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    domain = COSArray()
    domain.set_float_array([])
    raw.set_item("Domain", domain)
    raw.set_data(("{ " + body + " }").encode("utf-8"))
    return PDFunctionType4(raw).eval([])


# --------------------------------------------------------------------------
# Arithmetic operators
# --------------------------------------------------------------------------


def test_add() -> None:
    assert _eval("5 6 add") == pytest.approx([11.0])
    assert _eval("5 0.23 add") == pytest.approx([5.23], rel=1e-6)


def test_abs() -> None:
    assert _eval("-3 abs 2.1 abs -2.1 abs -7.5 abs") == pytest.approx(
        [3.0, 2.1, 2.1, 7.5]
    )


def test_atan() -> None:
    assert _eval("0 1 atan") == pytest.approx([0.0])
    assert _eval("1 0 atan") == pytest.approx([90.0])
    assert _eval("-100 0 atan") == pytest.approx([270.0])
    assert _eval("4 4 atan") == pytest.approx([45.0])


def test_ceiling() -> None:
    assert _eval("3.2 ceiling -4.8 ceiling 99 ceiling") == pytest.approx(
        [4.0, -4.0, 99.0]
    )


def test_cos() -> None:
    assert _eval("0 cos") == pytest.approx([1.0])
    assert _eval("90 cos") == pytest.approx([0.0], abs=1e-10)


def test_cvi() -> None:
    assert _eval("-47.8 cvi") == pytest.approx([-47.0])
    assert _eval("520.9 cvi") == pytest.approx([520.0])


def test_cvr() -> None:
    assert _eval("-47.8 cvr") == pytest.approx([-47.8], rel=1e-6)
    assert _eval("520.9 cvr") == pytest.approx([520.9], rel=1e-6)
    assert _eval("77 cvr") == pytest.approx([77.0])


def test_div() -> None:
    assert _eval("3 2 div") == pytest.approx([1.5])
    assert _eval("4 2 div") == pytest.approx([2.0])


def test_exp() -> None:
    assert _eval("9 0.5 exp") == pytest.approx([3.0])
    assert _eval("-9 -1 exp") == pytest.approx([-1.0 / 9.0], rel=1e-6)


def test_floor() -> None:
    assert _eval("3.2 floor -4.8 floor 99 floor") == pytest.approx(
        [3.0, -5.0, 99.0]
    )


def test_idiv() -> None:
    assert _eval("3 2 idiv") == pytest.approx([1.0])
    assert _eval("4 2 idiv") == pytest.approx([2.0])
    assert _eval("-5 2 idiv") == pytest.approx([-2.0])
    # Upstream raises ClassCastException; we surface OSError with a type-
    # mismatch message.
    with pytest.raises(OSError):
        _eval("4.4 2 idiv")


def test_ln() -> None:
    assert _eval("10 ln") == pytest.approx([2.30259], rel=1e-5)
    assert _eval("100 ln") == pytest.approx([4.60517], rel=1e-5)


def test_log() -> None:
    assert _eval("10 log") == pytest.approx([1.0])
    assert _eval("100 log") == pytest.approx([2.0])


def test_mod() -> None:
    assert _eval("5 3 mod") == pytest.approx([2.0])
    assert _eval("5 2 mod") == pytest.approx([1.0])
    assert _eval("-5 3 mod") == pytest.approx([-2.0])
    with pytest.raises(OSError):
        _eval("4.4 2 mod")


def test_mul() -> None:
    assert _eval("1 2 mul") == pytest.approx([2.0])
    assert _eval("1.5 2 mul") == pytest.approx([3.0])
    assert _eval("1.5 2.1 mul") == pytest.approx([3.15], rel=1e-3)


def test_neg() -> None:
    assert _eval("4.5 neg") == pytest.approx([-4.5])
    assert _eval("-3 neg") == pytest.approx([3.0])
    # Upstream's Integer.MIN_VALUE / Integer.MAX_VALUE special cases are
    # Java-overflow-specific and don't apply to Python's arbitrary-width
    # ints; skipped.


def test_round() -> None:
    assert _eval("3.2 round") == pytest.approx([3.0])
    assert _eval("6.5 round") == pytest.approx([7.0])
    assert _eval("-4.8 round") == pytest.approx([-5.0])
    assert _eval("-6.5 round") == pytest.approx([-6.0])
    assert _eval("99 round") == pytest.approx([99.0])


def test_sin() -> None:
    assert _eval("0 sin") == pytest.approx([0.0])
    assert _eval("90 sin") == pytest.approx([1.0])
    assert _eval("-90.0 sin") == pytest.approx([-1.0])


def test_sqrt() -> None:
    assert _eval("0 sqrt") == pytest.approx([0.0])
    assert _eval("1 sqrt") == pytest.approx([1.0])
    assert _eval("4 sqrt") == pytest.approx([2.0])
    assert _eval("4.4 sqrt") == pytest.approx([2.097617], rel=1e-6)
    # Upstream raises IllegalArgumentException; we raise OSError.
    with pytest.raises(OSError):
        _eval("-4.1 sqrt")


def test_sub() -> None:
    assert _eval("5 2 sub -7.5 1 sub") == pytest.approx([3.0, -8.5])


def test_truncate() -> None:
    assert _eval("3.2 truncate") == pytest.approx([3.0])
    assert _eval("-4.8 truncate") == pytest.approx([-4.0])
    assert _eval("99 truncate") == pytest.approx([99.0])


# --------------------------------------------------------------------------
# Bitwise / boolean operators
# --------------------------------------------------------------------------


def test_bitshift() -> None:
    assert _eval("7 3 bitshift 142 -3 bitshift") == pytest.approx([56.0, 17.0])


def test_eq() -> None:
    assert _eval(
        "7 7 eq 7 6 eq 7 -7 eq true true eq false true eq 7.7 7.7 eq"
    ) == pytest.approx([1.0, 0.0, 0.0, 1.0, 0.0, 1.0])


def test_ge() -> None:
    assert _eval("5 7 ge 7 5 ge 7 7 ge -1 2 ge") == pytest.approx(
        [0.0, 1.0, 1.0, 0.0]
    )


def test_gt() -> None:
    assert _eval("5 7 gt 7 5 gt 7 7 gt -1 2 gt") == pytest.approx(
        [0.0, 1.0, 0.0, 0.0]
    )


def test_le() -> None:
    assert _eval("5 7 le 7 5 le 7 7 le -1 2 le") == pytest.approx(
        [1.0, 0.0, 1.0, 1.0]
    )


def test_lt() -> None:
    assert _eval("5 7 lt 7 5 lt 7 7 lt -1 2 lt") == pytest.approx(
        [1.0, 0.0, 0.0, 1.0]
    )


def test_ne() -> None:
    assert _eval(
        "7 7 ne 7 6 ne 7 -7 ne true true ne false true ne 7.7 7.7 ne"
    ) == pytest.approx([0.0, 1.0, 1.0, 0.0, 1.0, 0.0])


def test_not() -> None:
    assert _eval("true not false not") == pytest.approx([0.0, 1.0])
    # Upstream PDFBox 3.0 negates ints (not bit-inverts). Mirror it.
    assert _eval("52 not -37 not") == pytest.approx([-52.0, 37.0])


def test_and() -> None:
    assert _eval("true true and true false and") == pytest.approx([1.0, 0.0])
    assert _eval("99 1 and 52 7 and") == pytest.approx([1.0, 4.0])


def test_or() -> None:
    assert _eval(
        "true true or true false or false false or"
    ) == pytest.approx([1.0, 1.0, 0.0])
    assert _eval("17 5 or 1 1 or") == pytest.approx([21.0, 1.0])


def test_xor() -> None:
    assert _eval(
        "true true xor true false xor false false xor"
    ) == pytest.approx([0.0, 1.0, 0.0])
    # Upstream's last assertion uses ``or`` not ``xor`` (12 3 or = 15);
    # we replicate that, including the trailing 4 from 7 3 xor.
    assert _eval("7 3 xor 12 3 or") == pytest.approx([4.0, 15.0])


# --------------------------------------------------------------------------
# Conditional operators
# --------------------------------------------------------------------------


def test_if() -> None:
    assert _eval("true { 2 1 add } if") == pytest.approx([3.0])
    assert _eval("false { 2 1 add } if") == []
    with pytest.raises(OSError):
        _eval("0 { 2 1 add } if")


def test_ifelse() -> None:
    assert _eval("true { 2 1 add } { 2 1 sub } ifelse") == pytest.approx([3.0])
    assert _eval("false { 2 1 add } { 2 1 sub } ifelse") == pytest.approx([1.0])


# --------------------------------------------------------------------------
# Stack operators
# --------------------------------------------------------------------------


def test_copy() -> None:
    # `true 1 2 3 3 copy` — bottom-up stack: [true,1,2,3,1,2,3].
    assert _eval("true 1 2 3 3 copy") == pytest.approx(
        [1.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0]
    )


def test_dup() -> None:
    assert _eval("true 1 2 dup") == pytest.approx([1.0, 1.0, 2.0, 2.0])
    assert _eval("true dup") == pytest.approx([1.0, 1.0])


def test_exch() -> None:
    assert _eval("true 1 exch") == pytest.approx([1.0, 1.0])
    assert _eval("1 2.5 exch") == pytest.approx([2.5, 1.0])


def test_index() -> None:
    assert _eval("1 2 3 4 0 index") == pytest.approx(
        [1.0, 2.0, 3.0, 4.0, 4.0]
    )
    assert _eval("1 2 3 4 3 index") == pytest.approx(
        [1.0, 2.0, 3.0, 4.0, 1.0]
    )


def test_pop() -> None:
    assert _eval("1 pop 7 2 pop") == pytest.approx([7.0])
    assert _eval("1 2 3 pop pop") == pytest.approx([1.0])


def test_roll() -> None:
    assert _eval("1 2 3 4 5 5 -2 roll") == pytest.approx(
        [3.0, 4.0, 5.0, 1.0, 2.0]
    )
    assert _eval("1 2 3 4 5 5 2 roll") == pytest.approx(
        [4.0, 5.0, 1.0, 2.0, 3.0]
    )
    assert _eval("1 2 3 3 0 roll") == pytest.approx([1.0, 2.0, 3.0])
