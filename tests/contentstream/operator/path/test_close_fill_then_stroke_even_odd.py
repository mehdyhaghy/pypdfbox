from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import CloseFillThenStrokeEvenOdd
from pypdfbox.contentstream.operator.path.close_fill_then_stroke_even_odd import (
    CloseFillThenStrokeEvenOdd as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert CloseFillThenStrokeEvenOdd.OPERATOR_NAME == "b*"


def test_get_name_returns_b_star() -> None:
    assert CloseFillThenStrokeEvenOdd().get_name() == "b*"


def test_re_export_matches_module_class() -> None:
    assert CloseFillThenStrokeEvenOdd is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``b*`` is a zero-operand operator (equivalent to h B*)."""
    CloseFillThenStrokeEvenOdd().process(Operator.get_operator("b*"), [])
