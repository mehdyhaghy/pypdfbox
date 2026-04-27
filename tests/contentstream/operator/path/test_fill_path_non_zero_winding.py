from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import FillPathNonZeroWinding
from pypdfbox.contentstream.operator.path.fill_path_non_zero_winding import (
    FillPathNonZeroWinding as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert FillPathNonZeroWinding.OPERATOR_NAME == "f"


def test_get_name_returns_lowercase_f() -> None:
    assert FillPathNonZeroWinding().get_name() == "f"


def test_re_export_matches_module_class() -> None:
    assert FillPathNonZeroWinding is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``f`` is a zero-operand operator."""
    FillPathNonZeroWinding().process(Operator.get_operator("f"), [])
