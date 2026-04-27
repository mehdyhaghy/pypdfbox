from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import ClipEvenOdd
from pypdfbox.contentstream.operator.path.clip_even_odd import (
    ClipEvenOdd as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert ClipEvenOdd.OPERATOR_NAME == "W*"


def test_get_name_returns_w_star() -> None:
    assert ClipEvenOdd().get_name() == "W*"


def test_re_export_matches_module_class() -> None:
    assert ClipEvenOdd is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``W*`` is a zero-operand clipping-region modifier (even-odd)."""
    ClipEvenOdd().process(Operator.get_operator("W*"), [])
