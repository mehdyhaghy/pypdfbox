"""Operand-validation parity fuzz for the lite path operator stubs.

Upstream PDFBox (3.0.7) validates the curve / rectangle path operators by
calling ``checkArrayTypesClass(operands, COSNumber.class)`` over the WHOLE
operand list — *not* just the consumed window. So a trailing non-number
(``x1 y1 x2 y2 x3 y3 /Name c`` or ``x y w h /Name re``) makes the operator a
silent no-op, rather than being accepted with the trailing operand ignored.

``l`` (LineTo) and ``m`` (MoveTo) upstream do NOT call
``checkArrayTypesClass`` — they only ``instanceof``-check ``operands.get(0)``
and ``operands.get(1)`` — so trailing operands of any type are tolerated.
These tests pin that asymmetry both ways.

Verified against upstream graphics operators:
``contentstream/operator/graphics/{CurveTo,CurveToReplicateInitialPoint,
CurveToReplicateFinalPoint,AppendRectangleToPath,LineTo,MoveTo}.java``.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.path import (
    AppendRectangle,
    CurveTo,
    CurveToReplicateFinalPoint,
    CurveToReplicateInitialPoint,
    LineTo,
    MoveTo,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString


def _num(value: float) -> COSFloat:
    return COSFloat(value)


def _nums(count: int) -> list[COSFloat]:
    return [COSFloat(float(i)) for i in range(count)]


# --------------------------------------------------------------------------
# whole-operand-list checkArrayTypesClass operators: c / v / y / re
# (count, processor class, operator name)
# --------------------------------------------------------------------------
WHOLE_LIST_OPS = [
    (6, CurveTo, "c"),
    (4, CurveToReplicateInitialPoint, "v"),
    (4, CurveToReplicateFinalPoint, "y"),
    (4, AppendRectangle, "re"),
]
WHOLE_LIST_IDS = ["c", "v", "y", "re"]


@pytest.mark.parametrize(
    ("count", "cls", "name"), WHOLE_LIST_OPS, ids=WHOLE_LIST_IDS
)
def test_whole_list_op_exact_numeric_operands_noop(
    count: int, cls: type, name: str
) -> None:
    """Exactly N numeric operands -> validation passes (debug-log no-op)."""
    cls().process(Operator.get_operator(name), _nums(count))


@pytest.mark.parametrize(
    ("count", "cls", "name"), WHOLE_LIST_OPS, ids=WHOLE_LIST_IDS
)
def test_whole_list_op_integer_operands_noop(
    count: int, cls: type, name: str
) -> None:
    """COSInteger is a COSNumber -> accepted just like COSFloat."""
    cls().process(
        Operator.get_operator(name),
        [COSInteger(i) for i in range(count)],
    )


@pytest.mark.parametrize(
    ("count", "cls", "name"), WHOLE_LIST_OPS, ids=WHOLE_LIST_IDS
)
def test_whole_list_op_empty_raises_missing_operand(
    count: int, cls: type, name: str
) -> None:
    with pytest.raises(MissingOperandException):
        cls().process(Operator.get_operator(name), [])


@pytest.mark.parametrize(
    ("count", "cls", "name"), WHOLE_LIST_OPS, ids=WHOLE_LIST_IDS
)
def test_whole_list_op_one_short_raises_missing_operand(
    count: int, cls: type, name: str
) -> None:
    with pytest.raises(MissingOperandException):
        cls().process(Operator.get_operator(name), _nums(count - 1))


@pytest.mark.parametrize(
    ("count", "cls", "name"), WHOLE_LIST_OPS, ids=WHOLE_LIST_IDS
)
def test_whole_list_op_non_number_in_window_is_silent_noop(
    count: int, cls: type, name: str
) -> None:
    """A non-number among the consumed operands -> silent no-op."""
    operands = _nums(count - 1) + [COSName("nope")]
    cls().process(Operator.get_operator(name), operands)


@pytest.mark.parametrize(
    ("count", "cls", "name"), WHOLE_LIST_OPS, ids=WHOLE_LIST_IDS
)
def test_whole_list_op_trailing_non_number_is_silent_noop(
    count: int, cls: type, name: str
) -> None:
    """The convergence fix: a TRAILING non-number past the consumed window
    must still make the operator a silent no-op, because upstream checks
    the WHOLE list (was a divergence when only ``operands[:N]`` was
    checked — the trailing operand was silently ignored and the op was
    treated as valid)."""
    operands = _nums(count) + [COSName("Trailing")]
    cls().process(Operator.get_operator(name), operands)


@pytest.mark.parametrize(
    ("count", "cls", "name"), WHOLE_LIST_OPS, ids=WHOLE_LIST_IDS
)
def test_whole_list_op_trailing_string_is_silent_noop(
    count: int, cls: type, name: str
) -> None:
    operands = _nums(count) + [COSString("xx")]
    cls().process(Operator.get_operator(name), operands)


def test_curve_to_six_numbers_plus_name_noop() -> None:
    """``0 0 50 100 100 0 /P c`` is a whole-list no-op (regression pin)."""
    operands = [
        _num(0.0),
        _num(0.0),
        _num(50.0),
        _num(100.0),
        _num(100.0),
        _num(0.0),
        COSName("P"),
    ]
    CurveTo().process(Operator.get_operator("c"), operands)


def test_append_rectangle_four_numbers_plus_name_noop() -> None:
    """``10 10 100 50 /P re`` is a whole-list no-op (regression pin)."""
    operands = [_num(10.0), _num(10.0), _num(100.0), _num(50.0), COSName("P")]
    AppendRectangle().process(Operator.get_operator("re"), operands)


# --------------------------------------------------------------------------
# first-two-only operators: l / m
# upstream does NOT call checkArrayTypesClass — only checks operands[0:2].
# Trailing operands of any type are tolerated.
# --------------------------------------------------------------------------
FIRST_TWO_OPS = [(LineTo, "l"), (MoveTo, "m")]
FIRST_TWO_IDS = ["l", "m"]


@pytest.mark.parametrize(("cls", "name"), FIRST_TWO_OPS, ids=FIRST_TWO_IDS)
def test_first_two_op_two_numbers_noop(cls: type, name: str) -> None:
    cls().process(Operator.get_operator(name), [_num(1.0), _num(2.0)])


@pytest.mark.parametrize(("cls", "name"), FIRST_TWO_OPS, ids=FIRST_TWO_IDS)
def test_first_two_op_empty_raises_missing_operand(
    cls: type, name: str
) -> None:
    with pytest.raises(MissingOperandException):
        cls().process(Operator.get_operator(name), [])


@pytest.mark.parametrize(("cls", "name"), FIRST_TWO_OPS, ids=FIRST_TWO_IDS)
def test_first_two_op_one_operand_raises_missing_operand(
    cls: type, name: str
) -> None:
    with pytest.raises(MissingOperandException):
        cls().process(Operator.get_operator(name), [_num(1.0)])


@pytest.mark.parametrize(("cls", "name"), FIRST_TWO_OPS, ids=FIRST_TWO_IDS)
def test_first_two_op_first_non_number_is_silent_noop(
    cls: type, name: str
) -> None:
    cls().process(Operator.get_operator(name), [COSName("x"), _num(2.0)])


@pytest.mark.parametrize(("cls", "name"), FIRST_TWO_OPS, ids=FIRST_TWO_IDS)
def test_first_two_op_second_non_number_is_silent_noop(
    cls: type, name: str
) -> None:
    cls().process(Operator.get_operator(name), [_num(1.0), COSName("y")])


@pytest.mark.parametrize(("cls", "name"), FIRST_TWO_OPS, ids=FIRST_TWO_IDS)
def test_first_two_op_trailing_non_number_is_tolerated(
    cls: type, name: str
) -> None:
    """Unlike c/v/y/re, ``l`` and ``m`` upstream ONLY check the first two
    operands (no ``checkArrayTypesClass`` over the whole list), so a
    trailing non-number does NOT veto the operator — it is tolerated and
    the op proceeds (here, the debug-log no-op). This is a deliberate
    asymmetry, not a divergence."""
    cls().process(
        Operator.get_operator(name),
        [_num(1.0), _num(2.0), COSName("Trailing")],
    )


@pytest.mark.parametrize(("cls", "name"), FIRST_TWO_OPS, ids=FIRST_TWO_IDS)
def test_first_two_op_integer_operands_noop(cls: type, name: str) -> None:
    cls().process(
        Operator.get_operator(name), [COSInteger(1), COSInteger(2)]
    )
