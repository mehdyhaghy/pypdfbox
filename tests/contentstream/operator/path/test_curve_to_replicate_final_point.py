from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import CurveToReplicateFinalPoint
from pypdfbox.contentstream.operator.path.curve_to_replicate_final_point import (
    CurveToReplicateFinalPoint as Direct,
)
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert CurveToReplicateFinalPoint.OPERATOR_NAME == "y"


def test_get_name_returns_y() -> None:
    assert CurveToReplicateFinalPoint().get_name() == "y"


def test_re_export_matches_module_class() -> None:
    assert CurveToReplicateFinalPoint is Direct


def test_process_with_four_operands_is_noop() -> None:
    """``y`` consumes four numbers (x1 y1 x3 y3)."""
    CurveToReplicateFinalPoint().process(
        Operator.get_operator("y"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(100.0), COSFloat(0.0)],
    )


def test_process_accepts_empty_operands_list() -> None:
    CurveToReplicateFinalPoint().process(Operator.get_operator("y"), [])
