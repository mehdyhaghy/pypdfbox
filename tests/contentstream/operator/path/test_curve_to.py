from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.path import CurveTo
from pypdfbox.contentstream.operator.path.curve_to import CurveTo as CurveToDirect
from pypdfbox.cos import COSFloat, COSName


def test_class_attribute_operator_name() -> None:
    assert CurveTo.OPERATOR_NAME == "c"


def test_get_name_returns_c() -> None:
    assert CurveTo().get_name() == "c"


def test_re_export_matches_module_class() -> None:
    assert CurveTo is CurveToDirect


def test_process_with_six_operands_is_noop() -> None:
    """``c`` consumes six numbers (x1 y1 x2 y2 x3 y3)."""
    CurveTo().process(
        Operator.get_operator("c"),
        [
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(50.0),
            COSFloat(100.0),
            COSFloat(100.0),
            COSFloat(0.0),
        ],
    )


def test_process_with_empty_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        CurveTo().process(Operator.get_operator("c"), [])


def test_process_with_five_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        CurveTo().process(
            Operator.get_operator("c"),
            [COSFloat(i) for i in range(5)],
        )


def test_process_with_non_number_operand_is_silent_no_op() -> None:
    """Upstream uses ``checkArrayTypesClass`` and returns silently when
    any operand is not a ``COSNumber``."""
    operands = [COSFloat(0.0)] * 5 + [COSName("nope")]
    CurveTo().process(Operator.get_operator("c"), operands)
