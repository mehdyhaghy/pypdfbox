from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import StrokePath
from pypdfbox.contentstream.operator.path.stroke_path import (
    StrokePath as StrokePathDirect,
)


def test_class_attribute_operator_name() -> None:
    assert StrokePath.OPERATOR_NAME == "S"


def test_get_name_returns_capital_s() -> None:
    assert StrokePath().get_name() == "S"


def test_re_export_matches_module_class() -> None:
    assert StrokePath is StrokePathDirect


def test_process_with_no_operands_is_noop() -> None:
    """``S`` is a zero-operand operator."""
    StrokePath().process(Operator.get_operator("S"), [])
