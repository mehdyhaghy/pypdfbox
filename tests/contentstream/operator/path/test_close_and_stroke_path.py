from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import CloseAndStrokePath
from pypdfbox.contentstream.operator.path.close_and_stroke_path import (
    CloseAndStrokePath as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert CloseAndStrokePath.OPERATOR_NAME == "s"


def test_get_name_returns_lowercase_s() -> None:
    assert CloseAndStrokePath().get_name() == "s"


def test_re_export_matches_module_class() -> None:
    assert CloseAndStrokePath is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``s`` is a zero-operand operator (equivalent to h S)."""
    CloseAndStrokePath().process(Operator.get_operator("s"), [])
