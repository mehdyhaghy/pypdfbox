from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import LegacyFillPath
from pypdfbox.contentstream.operator.path.legacy_fill_path import (
    LegacyFillPath as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert LegacyFillPath.OPERATOR_NAME == "F"


def test_get_name_returns_capital_f() -> None:
    assert LegacyFillPath().get_name() == "F"


def test_re_export_matches_module_class() -> None:
    assert LegacyFillPath is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``F`` is a zero-operand operator (PDF 1.0 alias of ``f``)."""
    LegacyFillPath().process(Operator.get_operator("F"), [])
