from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import (
    CloseFillThenStrokeNonZeroWinding,
)
from pypdfbox.contentstream.operator.path.close_fill_then_stroke_non_zero_winding import (
    CloseFillThenStrokeNonZeroWinding as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert CloseFillThenStrokeNonZeroWinding.OPERATOR_NAME == "b"


def test_get_name_returns_lowercase_b() -> None:
    assert CloseFillThenStrokeNonZeroWinding().get_name() == "b"


def test_re_export_matches_module_class() -> None:
    assert CloseFillThenStrokeNonZeroWinding is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``b`` is a zero-operand operator (equivalent to h B)."""
    CloseFillThenStrokeNonZeroWinding().process(
        Operator.get_operator("b"), []
    )
