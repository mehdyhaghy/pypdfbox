from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import ClipNonZeroWinding
from pypdfbox.contentstream.operator.path.clip_non_zero_winding import (
    ClipNonZeroWinding as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert ClipNonZeroWinding.OPERATOR_NAME == "W"


def test_get_name_returns_capital_w() -> None:
    assert ClipNonZeroWinding().get_name() == "W"


def test_re_export_matches_module_class() -> None:
    assert ClipNonZeroWinding is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``W`` is a zero-operand clipping-region modifier."""
    ClipNonZeroWinding().process(Operator.get_operator("W"), [])
