from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import EndPathNoOp
from pypdfbox.contentstream.operator.path.end_path_no_op import (
    EndPathNoOp as Direct,
)


def test_class_attribute_operator_name() -> None:
    assert EndPathNoOp.OPERATOR_NAME == "n"


def test_get_name_returns_n() -> None:
    assert EndPathNoOp().get_name() == "n"


def test_re_export_matches_module_class() -> None:
    assert EndPathNoOp is Direct


def test_process_with_no_operands_is_noop() -> None:
    """``n`` is a zero-operand operator that ends a path without
    painting it (commonly used together with a clipping operator)."""
    EndPathNoOp().process(Operator.get_operator("n"), [])
