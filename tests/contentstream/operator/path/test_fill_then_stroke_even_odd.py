from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import FillThenStrokeEvenOdd
from pypdfbox.contentstream.operator.path.fill_then_stroke_even_odd import (
    FillThenStrokeEvenOdd as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert FillThenStrokeEvenOdd.OPERATOR_NAME == "B*"


def test_get_name_returns_b_star() -> None:
    assert FillThenStrokeEvenOdd().get_name() == "B*"


def test_re_export_matches_module_class() -> None:
    assert FillThenStrokeEvenOdd is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``B*`` is a zero-operand operator."""
    FillThenStrokeEvenOdd().process(Operator.get_operator("B*"), [])
