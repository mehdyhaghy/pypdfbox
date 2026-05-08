from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.path import CurveToReplicateInitialPoint
from pypdfbox.contentstream.operator.path.curve_to_replicate_initial_point import (
    CurveToReplicateInitialPoint as Direct,
)
from pypdfbox.cos import COSFloat, COSName


def test_class_attribute_operator_name() -> None:
    assert CurveToReplicateInitialPoint.OPERATOR_NAME == "v"


def test_get_name_returns_v() -> None:
    assert CurveToReplicateInitialPoint().get_name() == "v"


def test_re_export_matches_module_class() -> None:
    assert CurveToReplicateInitialPoint is Direct


def test_process_with_four_operands_is_noop() -> None:
    """``v`` consumes four numbers (x2 y2 x3 y3)."""
    CurveToReplicateInitialPoint().process(
        Operator.get_operator("v"),
        [COSFloat(50.0), COSFloat(100.0), COSFloat(100.0), COSFloat(0.0)],
    )


def test_wave323_process_with_empty_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        CurveToReplicateInitialPoint().process(Operator.get_operator("v"), [])


def test_wave323_process_with_three_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        CurveToReplicateInitialPoint().process(
            Operator.get_operator("v"),
            [COSFloat(0.0), COSFloat(0.0), COSFloat(100.0)],
        )


def test_wave323_process_with_non_number_operand_is_silent_no_op() -> None:
    CurveToReplicateInitialPoint().process(
        Operator.get_operator("v"),
        [COSFloat(50.0), COSName("bad"), COSFloat(100.0), COSFloat(0.0)],
    )
