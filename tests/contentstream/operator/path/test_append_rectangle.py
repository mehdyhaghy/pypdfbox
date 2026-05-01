from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.path import AppendRectangle
from pypdfbox.contentstream.operator.path.append_rectangle import (
    AppendRectangle as AppendRectangleDirect,
)
from pypdfbox.cos import COSFloat, COSName


def test_class_attribute_operator_name() -> None:
    assert AppendRectangle.OPERATOR_NAME == "re"


def test_get_name_returns_re() -> None:
    assert AppendRectangle().get_name() == "re"


def test_re_export_matches_module_class() -> None:
    assert AppendRectangle is AppendRectangleDirect


def test_process_with_four_operands_is_noop() -> None:
    """``re`` consumes four numbers (x y width height)."""
    AppendRectangle().process(
        Operator.get_operator("re"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(100.0), COSFloat(50.0)],
    )


def test_process_with_empty_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        AppendRectangle().process(Operator.get_operator("re"), [])


def test_process_with_three_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        AppendRectangle().process(
            Operator.get_operator("re"),
            [COSFloat(0.0), COSFloat(0.0), COSFloat(10.0)],
        )


def test_process_with_non_number_operand_is_silent_no_op() -> None:
    """Upstream uses ``checkArrayTypesClass`` and returns silently when
    any operand is not a ``COSNumber``."""
    AppendRectangle().process(
        Operator.get_operator("re"),
        [COSFloat(0.0), COSFloat(0.0), COSName("bogus"), COSFloat(50.0)],
    )
