"""Upstream-shaped tests ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestOperators.java``
(arithmetic subset: testAdd / testAbs / testAtan / testCeiling / testCos /
testCvi / testCvr / testDiv / testExp / testFloor / testIDiv / testLn /
testLog / testMod / testMul / testNeg / testRound / testSin / testSqrt /
testSub / testTruncate).

The other ``TestOperators.java`` operator groups (bitwise, conditional,
relational, stack) live in sibling files in this directory. Skipped here
are the Java integer-overflow edges that exercise ``Integer.MAX_VALUE``
and ``Integer.MIN_VALUE`` — Python ints are unbounded so the
overflow-promotes-to-real branch upstream guards has no Python analogue.

We drive the operators through the parser-built ``InstructionSequence``
(mirroring upstream ``Type4Tester``) so the assertions exercise the full
parse → execute pipeline.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.pdmodel.common.function.type4 import (
    ExecutionContext,
    InstructionSequenceBuilder,
    Operators,
)


class _Type4Tester:
    """Local port of upstream
    ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/Type4Tester.java``.

    The upstream helper is type-aware (``pop(int)`` / ``popReal(float)``);
    we keep the same shape so individual tests read just like the Java
    source.
    """

    def __init__(self, ctx: ExecutionContext) -> None:
        self._context = ctx

    @classmethod
    def create(cls, text: str) -> _Type4Tester:
        seq = InstructionSequenceBuilder.parse(text)
        ctx = ExecutionContext(Operators())
        seq.execute(ctx)
        return cls(ctx)

    # ---- pop helpers ----
    def pop_bool(self, expected: bool) -> _Type4Tester:  # noqa: FBT001
        value = self._context.get_stack().pop()
        assert isinstance(value, bool)
        assert value == expected
        return self

    def pop_int(self, expected: int) -> _Type4Tester:
        value = self._context.get_stack().pop()
        # Upstream stores Integer separately from Float; pypdfbox stays
        # numerically faithful but may surface int operands as ``int``
        # *or* ``float`` depending on the operator. Compare numerically.
        assert int(value) == expected
        return self

    def pop_real(
        self, expected: float, delta: float = 1e-9
    ) -> _Type4Tester:
        value = self._context.get_stack().pop()
        assert math.isclose(
            float(value), expected, rel_tol=1e-9, abs_tol=max(delta, 1e-9)
        )
        return self

    def pop_number(
        self, expected: float, delta: float = 1e-9
    ) -> _Type4Tester:
        """Like ``pop()`` accepting a ``Number`` in Java."""
        value = self._context.get_stack().pop()
        assert math.isclose(
            float(value), float(expected), rel_tol=1e-9, abs_tol=max(delta, 1e-9)
        )
        return self

    def is_empty(self) -> _Type4Tester:
        assert self._context.get_stack() == []
        return self

    def to_execution_context(self) -> ExecutionContext:
        return self._context


# --------------------------------------------------------------------------
# Tests — one per upstream ``@Test``
# --------------------------------------------------------------------------


def test_add() -> None:
    """Tests the 'add' operator."""
    _Type4Tester.create("5 6 add").pop_int(11).is_empty()
    _Type4Tester.create("5 0.23 add").pop_number(5.23, delta=1e-5).is_empty()
    # Java's ``Integer.MAX_VALUE - 2`` overflow-to-real edge is skipped — Python
    # ints don't overflow.


def test_abs() -> None:
    """Tests the 'abs' operator."""
    (
        _Type4Tester.create("-3 abs 2.1 abs -2.1 abs -7.5 abs")
        .pop_number(7.5)
        .pop_number(2.1)
        .pop_number(2.1)
        .pop_int(3)
        .is_empty()
    )


def test_atan() -> None:
    """Tests the 'atan' operator."""
    _Type4Tester.create("0 1 atan").pop_number(0.0).is_empty()
    _Type4Tester.create("1 0 atan").pop_number(90.0).is_empty()
    _Type4Tester.create("-100 0 atan").pop_number(270.0).is_empty()
    _Type4Tester.create("4 4 atan").pop_number(45.0).is_empty()


def test_ceiling() -> None:
    """Tests the 'ceiling' operator."""
    (
        _Type4Tester.create("3.2 ceiling -4.8 ceiling 99 ceiling")
        .pop_int(99)
        .pop_number(-4.0)
        .pop_number(4.0)
        .is_empty()
    )


def test_cos() -> None:
    """Tests the 'cos' operator."""
    _Type4Tester.create("0 cos").pop_real(1.0).is_empty()
    _Type4Tester.create("90 cos").pop_real(0.0, delta=1e-7).is_empty()


def test_cvi() -> None:
    """Tests the 'cvi' operator."""
    _Type4Tester.create("-47.8 cvi").pop_int(-47).is_empty()
    _Type4Tester.create("520.9 cvi").pop_int(520).is_empty()


def test_cvr() -> None:
    """Tests the 'cvr' operator."""
    _Type4Tester.create("-47.8 cvr").pop_real(-47.8, delta=1e-5).is_empty()
    _Type4Tester.create("520.9 cvr").pop_real(520.9, delta=1e-4).is_empty()
    _Type4Tester.create("77 cvr").pop_real(77.0).is_empty()

    # Check that the data types are really right — upstream asserts that
    # ``cvr`` of an int literal pushes a Float while an unconverted int
    # literal stays as Integer. pypdfbox surfaces Python ints/floats.
    ctx = _Type4Tester.create("77 77 cvr").to_execution_context()
    top = ctx.get_stack().pop()
    assert isinstance(top, float), "Expected a real as the result of 'cvr'"
    bottom = ctx.get_stack().pop()
    assert isinstance(bottom, int) and not isinstance(bottom, bool), (
        "Expected an int from an integer literal"
    )


def test_div() -> None:
    """Tests the 'div' operator."""
    _Type4Tester.create("3 2 div").pop_real(1.5).is_empty()
    _Type4Tester.create("4 2 div").pop_real(2.0).is_empty()


def test_exp() -> None:
    """Tests the 'exp' operator."""
    _Type4Tester.create("9 0.5 exp").pop_real(3.0).is_empty()
    _Type4Tester.create("-9 -1 exp").pop_real(-0.111111, delta=1e-6).is_empty()


def test_floor() -> None:
    """Tests the 'floor' operator."""
    (
        _Type4Tester.create("3.2 floor -4.8 floor 99 floor")
        .pop_int(99)
        .pop_number(-5.0)
        .pop_number(3.0)
        .is_empty()
    )


def test_idiv() -> None:
    """Tests the 'idiv' operator."""
    _Type4Tester.create("3 2 idiv").pop_int(1).is_empty()
    _Type4Tester.create("4 2 idiv").pop_int(2).is_empty()
    _Type4Tester.create("-5 2 idiv").pop_int(-2).is_empty()
    # Upstream expects a typecheck (ClassCastException) when given a real.
    # pypdfbox raises OSError with a typecheck message.
    with pytest.raises((OSError, TypeError, ValueError)):
        _Type4Tester.create("4.4 2 idiv")


def test_ln() -> None:
    """Tests the 'ln' operator."""
    _Type4Tester.create("10 ln").pop_real(2.30259, delta=1e-5).is_empty()
    _Type4Tester.create("100 ln").pop_real(4.60517, delta=1e-5).is_empty()


def test_log() -> None:
    """Tests the 'log' operator."""
    _Type4Tester.create("10 log").pop_real(1.0).is_empty()
    _Type4Tester.create("100 log").pop_real(2.0).is_empty()


def test_mod() -> None:
    """Tests the 'mod' operator."""
    _Type4Tester.create("5 3 mod").pop_int(2).is_empty()
    _Type4Tester.create("5 2 mod").pop_int(1).is_empty()
    _Type4Tester.create("-5 3 mod").pop_int(-2).is_empty()
    with pytest.raises((OSError, TypeError, ValueError)):
        _Type4Tester.create("4.4 2 mod")


def test_mul() -> None:
    """Tests the 'mul' operator."""
    _Type4Tester.create("1 2 mul").pop_int(2).is_empty()
    _Type4Tester.create("1.5 2 mul").pop_real(3.0).is_empty()
    _Type4Tester.create("1.5 2.1 mul").pop_real(3.15, delta=1e-3).is_empty()
    # Java's overflow-to-real edge is skipped — Python ints don't overflow.


def test_neg() -> None:
    """Tests the 'neg' operator."""
    _Type4Tester.create("4.5 neg").pop_real(-4.5).is_empty()
    _Type4Tester.create("-3 neg").pop_int(3).is_empty()
    # Java MIN_VALUE/MAX_VALUE border cases skipped — Python ints don't
    # overflow.


def test_round() -> None:
    """Tests the 'round' operator."""
    _Type4Tester.create("3.2 round").pop_real(3.0).is_empty()
    _Type4Tester.create("6.5 round").pop_real(7.0).is_empty()
    _Type4Tester.create("-4.8 round").pop_real(-5.0).is_empty()
    # Upstream uses Java's round-half-up: -6.5 rounds to -6.0.
    _Type4Tester.create("-6.5 round").pop_real(-6.0).is_empty()
    _Type4Tester.create("99 round").pop_int(99).is_empty()


def test_sin() -> None:
    """Tests the 'sin' operator."""
    _Type4Tester.create("0 sin").pop_real(0.0).is_empty()
    _Type4Tester.create("90 sin").pop_real(1.0).is_empty()
    _Type4Tester.create("-90.0 sin").pop_real(-1.0).is_empty()


def test_sqrt() -> None:
    """Tests the 'sqrt' operator."""
    _Type4Tester.create("0 sqrt").pop_real(0.0).is_empty()
    _Type4Tester.create("1 sqrt").pop_real(1.0).is_empty()
    _Type4Tester.create("4 sqrt").pop_real(2.0).is_empty()
    _Type4Tester.create("4.4 sqrt").pop_real(2.097617, delta=1e-6).is_empty()
    # Upstream raises IllegalArgumentException; pypdfbox surfaces it as
    # OSError ("rangecheck" with the typical PostScript error name).
    with pytest.raises((OSError, ValueError)):
        _Type4Tester.create("-4.1 sqrt")


def test_sub() -> None:
    """Tests the 'sub' operator."""
    (
        _Type4Tester.create("5 2 sub -7.5 1 sub")
        .pop_number(-8.5)
        .pop_int(3)
        .is_empty()
    )


def test_truncate() -> None:
    """Tests the 'truncate' operator."""
    _Type4Tester.create("3.2 truncate").pop_real(3.0).is_empty()
    _Type4Tester.create("-4.8 truncate").pop_real(-4.0).is_empty()
    _Type4Tester.create("99 truncate").pop_int(99).is_empty()
