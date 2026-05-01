from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.path import MoveTo
from pypdfbox.contentstream.operator.path.move_to import MoveTo as MoveToDirect
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString


def test_class_attribute_operator_name() -> None:
    assert MoveTo.OPERATOR_NAME == "m"


def test_get_name_returns_m() -> None:
    assert MoveTo().get_name() == "m"


def test_re_export_matches_module_class() -> None:
    assert MoveTo is MoveToDirect


def test_process_with_two_operands_is_noop() -> None:
    handler = MoveTo()
    handler.process(
        Operator.get_operator("m"),
        [COSFloat(10.0), COSFloat(20.5)],
    )


def test_process_accepts_integer_operands() -> None:
    handler = MoveTo()
    handler.process(
        Operator.get_operator("m"),
        [COSInteger.get(0), COSInteger.get(0)],
    )


def test_process_with_empty_operands_raises_missing_operand() -> None:
    """Upstream throws ``MissingOperandException`` when arity < 2."""
    with pytest.raises(MissingOperandException):
        MoveTo().process(Operator.get_operator("m"), [])


def test_process_with_one_operand_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        MoveTo().process(Operator.get_operator("m"), [COSFloat(1.0)])


def test_process_with_non_number_first_operand_is_silent_no_op() -> None:
    """Upstream returns silently when ``base0`` is not a COSNumber."""
    MoveTo().process(
        Operator.get_operator("m"),
        [COSName("oops"), COSFloat(2.0)],
    )


def test_process_with_non_number_second_operand_is_silent_no_op() -> None:
    """Upstream returns silently when ``base1`` is not a COSNumber."""
    MoveTo().process(
        Operator.get_operator("m"),
        [COSFloat(1.0), COSString("nope")],
    )


def test_extra_trailing_operands_are_ignored() -> None:
    """Only the first two operands matter; trailing junk does not raise
    once the leading pair is valid (matches upstream's index-based
    access pattern)."""
    MoveTo().process(
        Operator.get_operator("m"),
        [COSFloat(1.0), COSFloat(2.0), COSName("trailing")],
    )
