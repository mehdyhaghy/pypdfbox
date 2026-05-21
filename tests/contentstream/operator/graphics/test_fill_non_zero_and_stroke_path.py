"""Hand-written tests for ``FillNonZeroAndStrokePath`` (``B``) — wave 1365.

Lite operator — fills + strokes the current path. Cluster #2 carries no
real rendering; this test fixes the operator-name surface and the no-op /
context-binding behaviour so the rendering cluster has a stable target.
"""

from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.graphics.fill_non_zero_and_stroke_path import (
    FillNonZeroAndStrokePath,
)
from pypdfbox.contentstream.operator.graphics.graphics_operator_processor import (
    GraphicsOperatorProcessor,
)


def test_get_name() -> None:
    assert FillNonZeroAndStrokePath().get_name() == "B"


def test_operator_name_constant() -> None:
    assert FillNonZeroAndStrokePath.OPERATOR_NAME == "B"


def test_inheritance_chain() -> None:
    assert issubclass(FillNonZeroAndStrokePath, GraphicsOperatorProcessor)


def test_process_with_no_operands_is_no_op() -> None:
    op = FillNonZeroAndStrokePath()
    op.process(Operator.get_operator("B"), [])


def test_process_without_context_is_no_op() -> None:
    op = FillNonZeroAndStrokePath()
    op.process(Operator.get_operator("B"), [])


def test_process_with_engine_context_logs_only() -> None:
    engine = PDFStreamEngine()
    op = FillNonZeroAndStrokePath()
    engine.add_operator(op)
    op.process(Operator.get_operator("B"), [])


def test_constructor_accepts_engine_context() -> None:
    engine = PDFStreamEngine()
    op = FillNonZeroAndStrokePath(engine)
    assert op.get_context() is engine


def test_get_graphics_context_alias() -> None:
    engine = PDFStreamEngine()
    op = FillNonZeroAndStrokePath()
    op.set_context(engine)
    assert op.get_graphics_context() is engine
