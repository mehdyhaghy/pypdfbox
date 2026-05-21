"""Hand-written tests for ``ClipEvenOddRule`` (``W*``) — wave 1365."""

from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.graphics.clip_even_odd_rule import (
    ClipEvenOddRule,
)
from pypdfbox.cos import COSFloat


def test_get_name() -> None:
    assert ClipEvenOddRule().get_name() == "W*"


def test_operator_name_constant() -> None:
    assert ClipEvenOddRule.OPERATOR_NAME == "W*"


def test_process_with_no_operands_is_no_op() -> None:
    op = ClipEvenOddRule()
    op.process(Operator.get_operator("W*"), [])


def test_process_with_extraneous_operands_is_silent() -> None:
    op = ClipEvenOddRule()
    op.process(Operator.get_operator("W*"), [COSFloat(1.0)])


def test_process_without_context_is_no_op() -> None:
    op = ClipEvenOddRule()
    op.process(Operator.get_operator("W*"), [])


def test_process_with_engine_context_logs_only() -> None:
    engine = PDFStreamEngine()
    op = ClipEvenOddRule()
    engine.add_operator(op)
    op.process(Operator.get_operator("W*"), [])


def test_constructor_accepts_engine_context() -> None:
    engine = PDFStreamEngine()
    op = ClipEvenOddRule(engine)
    assert op.get_context() is engine


def test_get_graphics_context_returns_bound_engine() -> None:
    engine = PDFStreamEngine()
    op = ClipEvenOddRule()
    op.set_context(engine)
    assert op.get_graphics_context() is engine
