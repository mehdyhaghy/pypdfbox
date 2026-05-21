"""Hand-written tests for ``ClipNonZeroRule`` (``W``) — wave 1365.

The operator is a lite stub at cluster #2 — it carries no operands and the
actual clipping-path intersection arrives with the rendering cluster. These
tests pin down the operator-name surface, the no-throw behaviour on empty
or extraneous operands, and the engine-context binding.
"""

from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.graphics.clip_non_zero_rule import (
    ClipNonZeroRule,
)
from pypdfbox.cos import COSFloat, COSName


def test_get_name() -> None:
    assert ClipNonZeroRule().get_name() == "W"


def test_operator_name_constant() -> None:
    assert ClipNonZeroRule.OPERATOR_NAME == "W"


def test_process_with_no_operands_is_no_op() -> None:
    op = ClipNonZeroRule()
    op.process(Operator.get_operator("W"), [])


def test_process_with_extraneous_operands_is_silent() -> None:
    # ``W`` carries no operands; spurious operands are tolerated.
    op = ClipNonZeroRule()
    op.process(
        Operator.get_operator("W"),
        [COSFloat(1.0), COSName.get_pdf_name("X")],
    )


def test_process_without_context_is_no_op() -> None:
    op = ClipNonZeroRule()
    op.process(Operator.get_operator("W"), [])


def test_process_with_engine_context_logs_only() -> None:
    engine = PDFStreamEngine()
    op = ClipNonZeroRule()
    engine.add_operator(op)
    op.process(Operator.get_operator("W"), [])


def test_constructor_accepts_engine_context() -> None:
    engine = PDFStreamEngine()
    op = ClipNonZeroRule(engine)
    assert op.get_context() is engine


def test_get_graphics_context_returns_bound_engine() -> None:
    engine = PDFStreamEngine()
    op = ClipNonZeroRule()
    op.set_context(engine)
    assert op.get_graphics_context() is engine
