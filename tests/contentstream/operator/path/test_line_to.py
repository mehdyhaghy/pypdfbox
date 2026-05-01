from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.path import LineTo
from pypdfbox.contentstream.operator.path.line_to import LineTo as LineToDirect
from pypdfbox.cos import COSFloat, COSName, COSString


def test_class_attribute_operator_name() -> None:
    assert LineTo.OPERATOR_NAME == "l"


def test_get_name_returns_l() -> None:
    assert LineTo().get_name() == "l"


def test_re_export_matches_module_class() -> None:
    assert LineTo is LineToDirect


def test_process_with_two_operands_is_noop() -> None:
    LineTo().process(
        Operator.get_operator("l"),
        [COSFloat(1.5), COSFloat(2.5)],
    )


def test_process_with_empty_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        LineTo().process(Operator.get_operator("l"), [])


def test_process_with_one_operand_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        LineTo().process(Operator.get_operator("l"), [COSFloat(1.0)])


def test_process_with_non_number_first_operand_is_silent_no_op() -> None:
    LineTo().process(
        Operator.get_operator("l"),
        [COSName("oops"), COSFloat(2.0)],
    )


def test_process_with_non_number_second_operand_is_silent_no_op() -> None:
    LineTo().process(
        Operator.get_operator("l"),
        [COSFloat(1.0), COSString("nope")],
    )
