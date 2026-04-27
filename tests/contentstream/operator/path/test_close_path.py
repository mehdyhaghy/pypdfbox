from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import ClosePath
from pypdfbox.contentstream.operator.path.close_path import (
    ClosePath as ClosePathDirect,
)


def test_class_attribute_operator_name() -> None:
    assert ClosePath.OPERATOR_NAME == "h"


def test_get_name_returns_h() -> None:
    assert ClosePath().get_name() == "h"


def test_re_export_matches_module_class() -> None:
    assert ClosePath is ClosePathDirect


def test_process_with_no_operands_is_noop() -> None:
    """``h`` is a zero-operand operator."""
    ClosePath().process(Operator.get_operator("h"), [])
