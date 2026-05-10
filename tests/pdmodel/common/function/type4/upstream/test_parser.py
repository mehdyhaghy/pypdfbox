"""Ported from upstream ``TestParser.java``.

Original:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestParser.java``
(PDFBox 3.0.x).

Tests the type-4 function parser.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4 import (
    ExecutionContext,
    InstructionSequenceBuilder,
    Operators,
)


class _Type4Tester:
    """Local port of upstream ``Type4Tester`` helper.

    Mirrors :class:`Type4Tester` in
    ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/Type4Tester.java``.
    """

    def __init__(self, ctx: ExecutionContext) -> None:
        self._context = ctx

    @classmethod
    def create(cls, text: str) -> _Type4Tester:
        instructions = InstructionSequenceBuilder.parse(text)
        ctx = ExecutionContext(Operators())
        instructions.execute(ctx)
        return cls(ctx)

    def pop(self, expected: object, delta: float = 0.0) -> _Type4Tester:
        value = self._context.get_stack().pop()
        if isinstance(expected, bool):
            assert value == expected
        elif isinstance(expected, float):
            assert abs(float(value) - expected) <= max(delta, 1e-7)
        else:
            # int comparison - the legacy fallback may have widened to
            # float so compare numerically rather than by exact type.
            assert float(value) == float(expected)
        return self

    def pop_real(self, expected: float, delta: float = 1e-7) -> _Type4Tester:
        value = self._context.get_stack().pop()
        assert abs(float(value) - expected) <= delta
        return self

    def is_empty(self) -> _Type4Tester:
        assert self._context.get_stack() == []
        return self

    def to_execution_context(self) -> ExecutionContext:
        return self._context


def test_parser_basics() -> None:
    """Test the very basics."""
    _Type4Tester.create("3 4 add 2 sub").pop(5).is_empty()


def test_nested() -> None:
    """Test nested blocks."""
    _Type4Tester.create("true { 2 1 add } { 2 1 sub } ifelse").pop(3).is_empty()
    _Type4Tester.create("{ true }").pop(True).is_empty()


def test_parse_float() -> None:
    """Tests parsing of real values."""
    assert InstructionSequenceBuilder.parse_real("0") == pytest.approx(0)
    assert InstructionSequenceBuilder.parse_real("1") == pytest.approx(1)
    assert InstructionSequenceBuilder.parse_real("+1") == pytest.approx(1)
    assert InstructionSequenceBuilder.parse_real("-1") == pytest.approx(-1)
    assert InstructionSequenceBuilder.parse_real("3.14157") == pytest.approx(
        3.14157, abs=1e-5
    )
    assert InstructionSequenceBuilder.parse_real("-1.2") == pytest.approx(
        -1.2, abs=1e-5
    )
    assert InstructionSequenceBuilder.parse_real("1.0E-5") == pytest.approx(
        1.0e-5, abs=1e-10
    )


def test_jira804() -> None:
    """Tests problematic functions from PDFBOX-804.

    Problems here were:

    1. no whitespace between ``mul`` and ``}`` (token was detected as ``mul}``)
    2. line breaks cause endless loops
    """
    _Type4Tester.create("1 {dup dup .72 mul exch 0 exch .38 mul}\n").pop(
        0.38, delta=1e-5
    ).pop(0.0).pop(0.72, delta=1e-5).pop(1.0).is_empty()
