from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import FillPathEvenOdd
from pypdfbox.contentstream.operator.path.fill_path_even_odd import (
    FillPathEvenOdd as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert FillPathEvenOdd.OPERATOR_NAME == "f*"


def test_get_name_returns_f_star() -> None:
    assert FillPathEvenOdd().get_name() == "f*"


def test_re_export_matches_module_class() -> None:
    assert FillPathEvenOdd is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``f*`` is a zero-operand operator."""
    FillPathEvenOdd().process(Operator.get_operator("f*"), [])
