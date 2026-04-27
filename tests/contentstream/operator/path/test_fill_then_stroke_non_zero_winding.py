from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import FillThenStrokeNonZeroWinding
from pypdfbox.contentstream.operator.path.fill_then_stroke_non_zero_winding import (
    FillThenStrokeNonZeroWinding as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert FillThenStrokeNonZeroWinding.OPERATOR_NAME == "B"


def test_get_name_returns_capital_b() -> None:
    assert FillThenStrokeNonZeroWinding().get_name() == "B"


def test_re_export_matches_module_class() -> None:
    assert FillThenStrokeNonZeroWinding is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``B`` is a zero-operand operator."""
    FillThenStrokeNonZeroWinding().process(Operator.get_operator("B"), [])
