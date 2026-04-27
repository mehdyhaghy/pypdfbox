from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import CurveTo
from pypdfbox.contentstream.operator.path.curve_to import CurveTo as CurveToDirect
from pypdfbox.cos import COSFloat


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


def test_process_accepts_empty_operands_list() -> None:
    CurveTo().process(Operator.get_operator("c"), [])
