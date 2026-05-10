"""Hand-written tests for :class:`InstructionSequenceBuilder`."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4 import (
    ExecutionContext,
    InstructionSequence,
    InstructionSequenceBuilder,
    Operators,
)


def test_parse_returns_instruction_sequence() -> None:
    seq = InstructionSequenceBuilder.parse("3 4 add")
    assert isinstance(seq, InstructionSequence)


def test_parse_simple_program() -> None:
    seq = InstructionSequenceBuilder.parse("3 4 add 2 sub")
    ctx = ExecutionContext(Operators())
    seq.execute(ctx)
    assert ctx.get_stack() == [5]


def test_parse_int_static() -> None:
    assert InstructionSequenceBuilder.parse_int("0") == 0
    assert InstructionSequenceBuilder.parse_int("123") == 123
    assert InstructionSequenceBuilder.parse_int("-7") == -7
    assert InstructionSequenceBuilder.parse_int("+7") == 7


def test_parse_real_static() -> None:
    assert InstructionSequenceBuilder.parse_real("3.14") == pytest.approx(3.14)
    assert InstructionSequenceBuilder.parse_real("-1.2") == pytest.approx(-1.2)
    assert InstructionSequenceBuilder.parse_real("1.0E-5") == pytest.approx(1.0e-5)


def test_token_distinguishes_int_real_name() -> None:
    """Mirrors upstream type-tagging: integer literals → addInteger,
    real literals → addReal, anything else → addName."""
    builder = InstructionSequenceBuilder()
    builder.token("42")
    builder.token("3.14")
    builder.token("add")
    instructions = builder.get_instruction_sequence().get_instructions()
    assert instructions[0] == 42
    assert isinstance(instructions[0], int)
    assert instructions[1] == pytest.approx(3.14)
    assert isinstance(instructions[1], float)
    assert instructions[2] == "add"


def test_brace_pushes_and_pops_sequence_stack() -> None:
    builder = InstructionSequenceBuilder()
    builder.token("{")
    builder.token("2")
    builder.token("3")
    builder.token("add")
    builder.token("}")
    main = builder.get_instruction_sequence()
    assert len(main.get_instructions()) == 1
    inner = main.get_instructions()[0]
    assert isinstance(inner, InstructionSequence)
    assert inner.get_instructions() == [2, 3, "add"]


def test_nested_braces() -> None:
    seq = InstructionSequenceBuilder.parse("{ 2 1 add }")
    ctx = ExecutionContext(Operators())
    seq.execute(ctx)
    # Top-level proc left on the stack auto-executes.
    assert ctx.get_stack() == [3]


def test_jira804_no_whitespace_before_brace() -> None:
    """Tokenizer treats '}' as its own token even without surrounding
    whitespace (PDFBOX-804 regression)."""
    seq = InstructionSequenceBuilder.parse(
        "1 {dup dup .72 mul exch 0 exch .38 mul}\n"
    )
    ctx = ExecutionContext(Operators())
    seq.execute(ctx)
    assert ctx.get_stack() == pytest.approx([1, 0.72, 0, 0.38])


def test_parse_real_pattern_matches_dot_only() -> None:
    """Upstream REAL_PATTERN is ``-?\\d*\\.\\d*([Ee]-?\\d+)?``; this
    matches strings like ``.5`` and ``5.`` too."""
    builder = InstructionSequenceBuilder()
    builder.token(".5")
    instructions = builder.get_instruction_sequence().get_instructions()
    assert instructions == [pytest.approx(0.5)]
    assert isinstance(instructions[0], float)


def test_unknown_token_becomes_name() -> None:
    """A token that matches neither the integer nor real pattern is
    registered as a name (operator lookup happens at execute time)."""
    builder = InstructionSequenceBuilder()
    builder.token("mystery")
    assert builder.get_instruction_sequence().get_instructions() == ["mystery"]


def test_get_instruction_sequence_returns_main() -> None:
    builder = InstructionSequenceBuilder()
    main = builder.get_instruction_sequence()
    assert isinstance(main, InstructionSequence)
    # Calling again returns the same instance.
    assert builder.get_instruction_sequence() is main
