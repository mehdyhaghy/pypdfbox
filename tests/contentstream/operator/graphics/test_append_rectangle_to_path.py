"""Hand-written tests for ``AppendRectangleToPath`` (``re``) — wave 1365.

Mirrors upstream operand validation:

* fewer than four operands → ``MissingOperandException``,
* any of the first four operands non-numeric → silent skip,
* numeric operands → no-op log invocation (rendering plumbing arrives with
  the rendering cluster).
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator import MissingOperandException
from pypdfbox.contentstream.operator.graphics.append_rectangle_to_path import (
    AppendRectangleToPath,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName


def test_get_name() -> None:
    assert AppendRectangleToPath().get_name() == "re"


def test_operator_name_constant() -> None:
    assert AppendRectangleToPath.OPERATOR_NAME == "re"


def test_process_no_operands_raises() -> None:
    op = AppendRectangleToPath()
    with pytest.raises(MissingOperandException):
        op.process(Operator.get_operator("re"), [])


def test_process_three_operands_raises() -> None:
    op = AppendRectangleToPath()
    with pytest.raises(MissingOperandException):
        op.process(
            Operator.get_operator("re"),
            [COSFloat(0.0), COSFloat(0.0), COSFloat(100.0)],
        )


def test_process_non_number_operand_is_silent_skip() -> None:
    op = AppendRectangleToPath()
    # Per upstream: non-number first-four → return without raising.
    op.process(
        Operator.get_operator("re"),
        [
            COSFloat(0.0),
            COSFloat(0.0),
            COSName.get_pdf_name("oops"),
            COSFloat(50.0),
        ],
    )


def test_process_happy_path_with_floats() -> None:
    op = AppendRectangleToPath()
    op.process(
        Operator.get_operator("re"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(100.0), COSFloat(50.0)],
    )


def test_process_happy_path_with_integers() -> None:
    op = AppendRectangleToPath()
    op.process(
        Operator.get_operator("re"),
        [
            COSInteger.get(0),
            COSInteger.get(0),
            COSInteger.get(100),
            COSInteger.get(50),
        ],
    )


def test_process_extra_trailing_operands_ignored() -> None:
    # Upstream slices the first four; trailing operands neither error nor
    # affect dispatch.
    op = AppendRectangleToPath()
    op.process(
        Operator.get_operator("re"),
        [
            COSFloat(1.0),
            COSFloat(2.0),
            COSFloat(3.0),
            COSFloat(4.0),
            COSName.get_pdf_name("trailing"),
        ],
    )


def test_constructor_accepts_engine_context() -> None:
    engine = PDFStreamEngine()
    op = AppendRectangleToPath(engine)
    assert op.get_context() is engine
