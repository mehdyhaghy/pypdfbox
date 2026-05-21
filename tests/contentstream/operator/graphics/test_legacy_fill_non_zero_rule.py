"""Hand-written tests for ``LegacyFillNonZeroRule`` (``F``) — wave 1365.

The legacy ``F`` operator is the pre-PDF 1.2 alias for ``f``. Upstream
subclasses :class:`FillNonZeroRule` and only overrides the operator name.
"""

from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.graphics.fill_non_zero_rule import (
    FillNonZeroRule,
)
from pypdfbox.contentstream.operator.graphics.legacy_fill_non_zero_rule import (
    LegacyFillNonZeroRule,
)


def test_get_name() -> None:
    assert LegacyFillNonZeroRule().get_name() == "F"


def test_operator_name_constant() -> None:
    assert LegacyFillNonZeroRule.OPERATOR_NAME == "F"


def test_inheritance_chain() -> None:
    # Upstream identity preserved: F is just a rename of f.
    assert issubclass(LegacyFillNonZeroRule, FillNonZeroRule)


def test_process_with_no_operands_is_no_op() -> None:
    op = LegacyFillNonZeroRule()
    op.process(Operator.get_operator("F"), [])


def test_process_with_engine_context() -> None:
    engine = PDFStreamEngine()
    op = LegacyFillNonZeroRule()
    engine.add_operator(op)
    op.process(Operator.get_operator("F"), [])


def test_legacy_and_modern_are_distinct_instances() -> None:
    legacy = LegacyFillNonZeroRule()
    modern = FillNonZeroRule()
    assert legacy.get_name() == "F"
    assert modern.get_name() == "f"
    assert legacy is not modern


def test_constructor_accepts_engine_context() -> None:
    engine = PDFStreamEngine()
    op = LegacyFillNonZeroRule(engine)
    assert op.get_context() is engine
